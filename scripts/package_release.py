#!/usr/bin/env python3
"""Create an immutable app-host bundle from clean repositories and digest-pinned images."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from configure_domains import generate

ROOT = Path(__file__).resolve().parents[1]
APPS = ('datalake', 'crust', 'portal', 'sites')
SERVICES = (*APPS, 'auth', 'web', 'caddy')
REPOS = ('guten', *(f'guten-{name}' for name in APPS))
IMAGE = re.compile(r'[a-z0-9][a-z0-9./:_-]*@sha256:[a-f0-9]{64}')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root):
    revisions = {}
    for name in REPOS:
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root/name), *args], text=True).strip()
        if git('status', '--porcelain'):
            raise ValueError(f'{name} has uncommitted changes; release sources must be clean.')
        revisions[name] = git('rev-parse', 'HEAD')
    return revisions


def package(target, release_id, images, domains, revisions, source_root):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', release_id):
        raise ValueError('Use a lowercase release ID with letters, digits and hyphens.')
    if set(images) != set(SERVICES) or any(not isinstance(v,str) or not IMAGE.fullmatch(v) for v in images.values()):
        raise ValueError('Provide all seven service images as registry/repository@sha256:<64 hex digits>.')
    target = target.resolve()
    if target.exists(): raise ValueError('Output already exists; release bundles are never overwritten.')
    target.parent.mkdir(parents=True, exist_ok=True)
    install = Path('/opt/guten/releases')/release_id
    with tempfile.TemporaryDirectory(prefix='.guten-release-', dir=target.parent) as directory:
        stage=Path(directory)
        gateway=generate(domains, stage/'gateway')
        docker=shutil.which('docker') or '/usr/local/bin/docker'
        raw=subprocess.check_output([docker,'compose','-f',str(source_root/'guten/deploy/compose.apps.yaml'),'-f',str(gateway/'compose.gateway.yaml'),'config','--no-interpolate','--no-path-resolution','--format','json'],text=True)
        config=json.loads(raw)
        config.pop('x-runtime',None)
        config['name']='guten-prod'
        config['networks']={'default':{'name':'guten-prod'}}
        config['volumes']={name:{'external':True,'name':'guten-'+name.replace('_','-')} for name in ('caddy_data','caddy_config')}
        for name,service in config['services'].items():
            service.pop('build',None)
            service['image']=images[name]
            service['platform']='linux/amd64'
            for mount in service.get('volumes',[]):
                if mount.get('type')=='bind':
                    mount['source']=str(install/'gateway'/Path(mount['source']).name) if name in ('web','caddy') else '/srv/guten/assets'
                    mount['bind']={'create_host_path':False}
        config['services']['datalake']['environment']['DATABASE_SSL_CA_FILE']='/run/config/database_ca'
        config['services']['datalake']['volumes']=[{'type':'bind','source':'/etc/guten/secrets/database_ca.crt','target':'/run/config/database_ca','read_only':True,'bind':{'create_host_path':False}}]
        secret_names={'database_url':'database_url','oauth_config':'oauth2-proxy.cfg','github_client_secret':'github_client_secret','oauth_cookie_secret':'oauth_cookie_secret'}
        config['secrets']={name:{'file':'/etc/guten/secrets/'+filename} for name,filename in secret_names.items()}
        # Generated deployment overlays are superseded by this merged, fully resolved file.
        (gateway/'compose.gateway.yaml').unlink()
        (stage/'compose.json').write_text(json.dumps(config,indent=2)+'\n')
        shutil.copy2(ROOT/'scripts/deploy_release.py', stage/'deploy_release.py')
        migrations={p.name:sha(p) for p in sorted((source_root/'guten-datalake/scripts/database/migrations').glob('*.sql'))}
        if not migrations: raise ValueError('No database migration contract found.')
        for path in stage.rglob('*'):
            if path.is_file(): path.chmod(0o644)
        files={p.relative_to(stage).as_posix():sha(p) for p in stage.rglob('*') if p.is_file()}
        manifest={'format':1,'release':release_id,'install_dir':str(install),'source_commits':revisions,'images':images,'migrations':migrations,'files':files,'smoke_urls':['https://'+domains['portal']+'/oauth2/sign_in', *['https://'+s['host']+'/health' for s in domains['sites']]]}
        (stage/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
        if '${' in (stage/'compose.json').read_text(): raise ValueError('Unresolved Compose environment substitution.')
        subprocess.run([docker,'compose','-f',str(stage/'compose.json'),'config','--quiet'],check=True)
        # Rename within one parent filesystem; an interrupted build has no completed bundle.
        stage.rename(target)
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',required=True)
    p.add_argument('--images',type=Path,required=True,help='JSON map of service name to immutable registry image digest.')
    p.add_argument('--domains',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(package(a.output,a.id,json.loads(a.images.read_text()),json.loads(a.domains.read_text()),sources(ROOT.parent),ROOT.parent))
