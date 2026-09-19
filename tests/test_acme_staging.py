import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_acme_staging as staging

class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.bundle=self.root/'release';(self.bundle/'gateway').mkdir(parents=True)
        self.manifest={'images':{'caddy':'caddy@sha256:'+'a'*64}}
    def test_rejects_full_publication_release(self):
        (self.bundle/'gateway/domains.json').write_text(json.dumps({'portal':'portal.guten.ink','sites':[{'site':'guten','host':'guten.ink'}]}))
        with patch.object(staging,'verify',return_value=self.manifest),self.assertRaises(ValueError):staging.prepare(self.bundle,self.root/'out')
        self.assertFalse((self.root/'out').exists())
    def test_no_production_storage_or_application_network(self):
        (self.bundle/'gateway/domains.json').write_text(json.dumps({'portal':'portal.guten.ink','portal_only':True,'sites':[]}))
        with patch.object(staging,'verify',return_value=self.manifest):result=staging.prepare(self.bundle,self.root/'out')
        compose=json.loads((result/'compose.json').read_text())
        self.assertEqual(compose['name'],'guten-acme-staging')
        self.assertNotIn('networks',compose)
        self.assertEqual(compose['volumes'],{'data':{},'config':{}})
        self.assertNotIn('reverse_proxy',(result/'Caddyfile').read_text())
        self.assertIn('acme-staging-v02',(result/'Caddyfile').read_text())

if __name__=='__main__':unittest.main()
