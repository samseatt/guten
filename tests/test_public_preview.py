import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_public_preview as preview

class PublicPreviewTests(unittest.TestCase):
    def test_preview_cannot_publish_app_backend_or_collide_with_live_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);release=root/'release';release.mkdir()
            source={'services':{'sites':{'image':'example/sites@sha256:'+'a'*64,'environment':{},'depends_on':{'crust':{}}},'web':{'image':'example/web@sha256:'+'b'*64,'ports':['80:8080'],'healthcheck':{'test':['CMD','true']},'depends_on':{'auth':{}}}}}
            (release/'compose.json').write_text(json.dumps(source))
            domains={'portal':'portal.guten.ink','sites':[{'host':'guten.ink','site':'guten'}]}
            with patch.object(preview,'verify'):
                target=preview.prepare(release,domains,root/'preview')
            result=json.loads((target/'compose.json').read_text())
            self.assertEqual(set(result['services']),{'preview_sites','preview_web'})
            self.assertEqual(result['services']['preview_web']['ports'],['127.0.0.1:18082:8080'])
            self.assertNotIn('ports',result['services']['preview_sites'])
            self.assertNotIn('secrets',result)
            self.assertEqual(result['networks'],{'default':{'external':True,'name':'guten-prod'}})
            self.assertIn('set $frontend_backend preview_sites:3000;',(target/'gateway/nginx.conf').read_text())
            self.assertEqual(json.loads((release/'compose.json').read_text()),source)

if __name__=='__main__':unittest.main()
