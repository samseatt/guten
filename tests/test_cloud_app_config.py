import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import configure_cloud_app as app

class CloudAppConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)/'secrets';app.prepare(self.state)
    def configured(self):
        p=self.state/'oauth2-proxy.cfg';p.write_text(p.read_text().replace('REPLACE_GITHUB_CLIENT_ID','Ov23exampleclientid'))
        (self.state/'github_client_secret').write_text('a'*40)
    def test_prepare_preserves_existing_values(self):
        self.configured();cookie=(self.state/'oauth_cookie_secret').read_text()
        app.prepare(self.state)
        self.assertEqual(app.validate_auth(self.state)['github_client_secret'],'a'*40)
        self.assertEqual((self.state/'oauth_cookie_secret').read_text(),cookie)
    def test_placeholder_and_insecure_cookie_setting_rejected(self):
        with self.assertRaises(ValueError):app.validate_auth(self.state)
        self.configured();p=self.state/'oauth2-proxy.cfg';p.write_text(p.read_text().replace('cookie_secure = true','cookie_secure = false'))
        with self.assertRaises(ValueError):app.validate_auth(self.state)
    def test_world_readable_secret_rejected(self):
        self.configured();(self.state/'github_client_secret').chmod(0o644)
        with self.assertRaises(ValueError):app.validate_auth(self.state)
    def test_write_token_rejected_before_install(self):
        (self.state/'ghcr_read_token').write_text('ghp_'+'a'*36)
        class Response:
            headers={'X-OAuth-Scopes':'read:packages, write:packages'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"login":"samseatt"}'
        with patch.object(app.urllib.request,'urlopen',return_value=Response()):
            with self.assertRaises(ValueError):app.validate_token(self.state)

if __name__=='__main__':unittest.main()
