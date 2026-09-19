"""Registry retry safety; fake Docker responses and no network."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import publish_release_images as publisher

class RegistryPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'build.json'
        self.revision='a'*40
        self.record={'platform':'linux/amd64','source_commits':{},'images':{}}
        self.locals={}
        for name in ('datalake','crust','portal','sites'):
            self.record['source_commits']['guten-'+name]=self.revision
            tag='ghcr.io/example/guten-'+name+':'+self.revision
            self.record['images'][name]={'tag':tag,'source_commit':self.revision,'image_id':'sha256:'+'b'*64}
            self.locals[tag]={'Id':'sha256:'+'b'*64,'Os':'linux','Architecture':'amd64','Config':{'Labels':{'org.opencontainers.image.revision':self.revision}},'RepoDigests':[tag.rsplit(':',1)[0]+'@sha256:'+'c'*64]}
        self.path.write_text(json.dumps(self.record))

    def test_modified_last_image_prevents_all_uploads(self):
        tag=self.record['images']['sites']['tag'];self.locals[tag]['Id']='different'
        with patch.object(publisher,'inspect',side_effect=lambda tag:self.locals[tag]),patch.object(publisher.subprocess,'run') as run:
            with self.assertRaises(ValueError):publisher.publish(self.path)
            run.assert_not_called()

    def test_failed_upload_preserves_progress_and_retry_never_builds(self):
        with patch.object(publisher,'inspect',side_effect=lambda tag:self.locals[tag]),patch.object(publisher.subprocess,'run',side_effect=[None,subprocess.CalledProcessError(1,['docker','push'])]):
            with self.assertRaises(subprocess.CalledProcessError):publisher.publish(self.path)
        after=json.loads(self.path.read_text())
        self.assertIn('digest',after['images']['datalake'])
        self.assertNotIn('digest',after['images']['crust'])
        with patch.object(publisher,'inspect',side_effect=lambda tag:self.locals[tag]),patch.object(publisher.subprocess,'run') as run:
            result=publisher.publish(self.path)
            self.assertTrue(all(call.args[0][:2]==['docker','push'] for call in run.call_args_list))
        self.assertTrue(all('digest' in entry for entry in result['images'].values()))

    def test_missing_image_id_refuses_unverifiable_old_record(self):
        del self.record['images']['datalake']['image_id'];self.path.write_text(json.dumps(self.record))
        with patch.object(publisher,'inspect',side_effect=lambda tag:self.locals[tag]),patch.object(publisher.subprocess,'run') as run:
            with self.assertRaises(KeyError):publisher.publish(self.path)
            run.assert_not_called()

if __name__=='__main__':unittest.main()
