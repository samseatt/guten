"""Release controller tests; Docker rendering only, no daemon/deployment/registry writes."""
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import package_release as packaging
import deploy_release as deployment
import build_release_images as building


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.images={name:'example.com/guten/'+name+'@sha256:'+'a'*64 for name in packaging.SERVICES}
        self.revisions={name:'b'*40 for name in packaging.REPOS}
        self.domains={'portal':'portal.example.com','sites':[{'host':'example.com','site':'guten'}]}

    def bundle(self,name='release-a'):
        return packaging.package(self.root/name,name,self.images,self.domains,self.revisions,ROOT.parent)

    def test_rendered_bundle_is_pinned_portable_and_has_no_local_ports_or_builds(self):
        bundle=self.bundle()
        manifest=deployment.verify(bundle)
        compose=json.loads((bundle/'compose.json').read_text())
        self.assertEqual(set(compose['services']),set(packaging.SERVICES))
        for name,service in compose['services'].items():
            self.assertNotIn('build',service)
            self.assertEqual(service['platform'],'linux/amd64')
            if name!='caddy': self.assertFalse(service.get('ports'))
        self.assertEqual(compose['services']['datalake']['environment']['DATABASE_SSL_CA_FILE'],'/run/config/database_ca')
        self.assertTrue(all(v['external'] for v in compose['volumes'].values()))
        self.assertNotIn(str(ROOT),(bundle/'compose.json').read_text())
        self.assertEqual(len(manifest['migrations']),2)
        self.assertEqual(compose['services']['auth']['environment']['OAUTH2_PROXY_COOKIE_SECURE'],'true')

    def test_refuses_mutable_missing_images_and_existing_output(self):
        for images in ({},dict(self.images,portal='example.com/portal:latest')):
            with self.assertRaises(ValueError): packaging.package(self.root/'bad','bad',images,self.domains,self.revisions,ROOT.parent)
        self.bundle()
        with self.assertRaises(ValueError): self.bundle()

    def test_tampering_is_detected_before_any_docker_call(self):
        bundle=self.bundle()
        (bundle/'gateway/nginx.conf').write_text('changed')
        with patch.object(deployment,'preflight') as preflight:
            with self.assertRaises(ValueError): deployment.apply(bundle,self.root/'state')
            preflight.assert_not_called()

    def test_success_failure_and_rollback_state(self):
        first=self.bundle('release-a'); second=self.bundle('release-b')
        state_dir=self.root/'state'
        # Fixture bundles simulate their installed location; real CLI enforces /opt/guten.
        for bundle in (first,second):
            path=bundle/'release.json'; m=json.loads(path.read_text()); m['install_dir']=str(bundle); path.write_text(json.dumps(m))
        with patch.object(deployment,'RELEASES',self.root),patch.object(deployment,'preflight'),patch.object(deployment,'compose') as compose,patch.object(deployment,'smoke') as smoke:
            deployment.apply(first,state_dir)
            smoke.side_effect=RuntimeError('failed HTTPS readiness')
            with self.assertRaises(RuntimeError): deployment.apply(second,state_dir)
            state=json.loads((state_dir/'state.json').read_text())
            self.assertEqual(state['last_successful'],'release-a')
            self.assertEqual(deployment.rollback_target(state),first)
            smoke.side_effect=None
            deployment.apply(None,state_dir)
            deployment.apply(second,state_dir)
            state=json.loads((state_dir/'state.json').read_text())
            self.assertEqual(state['previous'],'release-a')
            self.assertEqual(state['last_successful'],'release-b')
            self.assertEqual(deployment.rollback_target(state),first)
            self.assertFalse(any('down' in call.args or '--volumes' in call.args for call in compose.call_args_list))

    def test_schema_or_image_preflight_failure_preserves_state(self):
        bundle=self.bundle()
        path=bundle/'release.json'; m=json.loads(path.read_text()); m['install_dir']=str(bundle); path.write_text(json.dumps(m))
        with patch.object(deployment,'RELEASES',self.root),patch.object(deployment,'preflight',side_effect=RuntimeError('schema mismatch')),patch.object(deployment,'compose') as compose:
            with self.assertRaises(RuntimeError): deployment.apply(bundle,self.root/'state')
            compose.assert_not_called()
            self.assertFalse((self.root/'state/state.json').exists())

    def test_image_provenance_mismatch_is_rejected_before_database_probe(self):
        from subprocess import CompletedProcess
        manifest={'images':self.images,'source_commits':self.revisions,'migrations':{'001.sql':'c'*64}}
        inspected=[{'Os':'linux','Architecture':'amd64','Config':{'Labels':{'org.opencontainers.image.revision':'d'*40}}}]
        with patch.object(deployment,'command',return_value=CompletedProcess([],0,json.dumps(inspected))),patch.object(deployment,'compose') as compose:
            with self.assertRaisesRegex(ValueError,'revision'): deployment.preflight(self.root,manifest)
            self.assertEqual(compose.call_count,1)  # Pull only; no DB probe/up.

    def test_migration_preflight_uses_read_only_transaction_and_exact_checksums(self):
        from subprocess import CompletedProcess
        manifest={'images':self.images,'source_commits':self.revisions,'migrations':{'001.sql':'c'*64}}
        inspected=[{'Os':'linux','Architecture':'amd64','Config':{'Labels':{'org.opencontainers.image.revision':'b'*40}}}]
        with patch.object(deployment,'command',return_value=CompletedProcess([],0,json.dumps(inspected))),patch.object(deployment,'compose') as compose:
            deployment.preflight(self.root,manifest)
            args=compose.call_args.args
            self.assertIn('SET TRANSACTION READ ONLY',args[-2])
            self.assertEqual(json.loads(args[-1]),manifest['migrations'])
            self.assertIn('--no-deps',args)

    def test_build_contexts_exclude_ignored_secrets_and_dirty_sources_are_refused(self):
        source=self.root/'sources'; source.mkdir()
        for name in packaging.REPOS:
            repo=source/name; repo.mkdir()
            (repo/'Dockerfile').write_text('FROM scratch\n')
            (repo/'.gitignore').write_text('secret.env\n')
            (repo/'secret.env').write_text('test-only-secret')
            for args in (['init','-q'],['add','Dockerfile','.gitignore'],['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture']):
                subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
        docker_calls=[]
        original=building.run
        def execute(args,**kwargs):
            if args[0]=='docker':
                self.assertEqual(args[1],'build')  # No implicit push.
                context=Path(args[-1])
                self.assertTrue((context/'Dockerfile').exists())
                self.assertFalse((context/'secret.env').exists())
                self.assertFalse((context/'.git').exists())
                docker_calls.append(args)
                return subprocess.CompletedProcess(args,0)
            return original(args,**kwargs)
        output=self.root/'build.json'
        with patch.object(building,'ROOT',source/'guten'),patch.object(building,'run',side_effect=execute),patch.object(building,'inspect',return_value={'Id':'sha256:'+'c'*64}),patch.object(sys,'argv',['build','--registry','example.com/guten','--output',str(output)]):
            building.main()
        self.assertEqual(len(docker_calls),4)
        self.assertTrue(all('--label' in args and 'linux/amd64' in args for args in docker_calls))
        self.assertIn('NEXT_PUBLIC_AUTH_ENABLED=true',next(args for args in docker_calls if 'guten-portal:' in args[args.index('-t')+1]))
        (source/'guten-sites/Dockerfile').write_text('changed')
        with self.assertRaisesRegex(ValueError,'uncommitted'): packaging.sources(source)

    def test_first_failed_deployment_has_no_rollback_target(self):
        with self.assertRaises(ValueError): deployment.rollback_target({'outcome':'failed','attempted':'release-a'})


if __name__=='__main__': unittest.main()
