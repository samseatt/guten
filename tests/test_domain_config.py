"""Domain manifests are configuration inputs at a security boundary."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from configure_domains import generate

class DomainConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target=Path(self.temp.name)/'generated'
        self.manifest={'portal':'portal.guten.test','sites':[{'host':'alpha.guten.test','site':'alpha','aliases':['www.alpha.guten.test']}]}

    def test_test_mode_uses_internal_ca_and_loopback_only(self):
        p=generate(self.manifest,self.target,True)
        self.assertIn('tls internal',(p/'Caddyfile').read_text())
        cfg=(p/'compose.gateway.yaml').read_text()
        self.assertIn('127.0.0.1:14443:14443',cfg)
        self.assertIn('ports: !override []',cfg)
        self.assertIn('OAUTH2_PROXY_COOKIE_SECURE: "true"',cfg)
        self.assertEqual(json.loads((p/'domains.json').read_text()),self.manifest)
        with self.assertRaises(ValueError):generate(self.manifest,p,True)

    def test_invalid_or_conflicting_names_are_rejected(self):
        cases=[{'host':'alpha.guten.test;bad','site':'alpha'}, {'host':'alpha.guten.test','site':'../alpha'}, {'host':'portal.guten.test','site':'alpha'}, {'host':'alpha.guten.test','site':'alpha','aliases':['alpha.guten.test']}]
        for entry in cases:
            with self.subTest(entry=entry),self.assertRaises(ValueError):
                generate({'portal':self.manifest['portal'],'sites':[entry]},self.target,True)
        duplicate={'portal':self.manifest['portal'],'sites':[{'host':'a.guten.test','site':'alpha'},{'host':'b.guten.test','site':'alpha'}]}
        with self.assertRaises(ValueError):generate(duplicate,self.target,True)

    def test_test_domains_cannot_be_accidentally_sent_to_public_ca(self):
        with self.assertRaises(ValueError):generate(self.manifest,self.target,False)
        self.manifest['portal']='portal.guten.ink'
        with self.assertRaises(ValueError):generate(self.manifest,self.target,True)

if __name__=='__main__':unittest.main()
