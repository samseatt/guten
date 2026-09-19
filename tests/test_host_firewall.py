"""Portable validation; packet-level Linux coverage is in test_host_firewall_linux.py."""
import sys
import subprocess
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from configure_host_firewall import render


class FirewallTests(unittest.TestCase):
    def test_invalid_addresses_and_roles(self):
        for args in [('database','8.8.8.8','10.0.0.2'),('database','10.0.0.1; reboot','10.0.0.2'),('other','10.0.0.1','10.0.0.2')]:
            with self.assertRaises(ValueError):
                render(*args)

    def test_shell_parses_both_roles(self):
        for role in ('application','database'):
            result = subprocess.run(['sh','-n'], input=render(role,'10.0.0.1','10.0.0.2'), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
