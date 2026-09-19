import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_backup_operations import combined


class LauncherTests(unittest.TestCase):
    def build(self,source):
        with patch('prepare_backup_operations.retention',return_value=source),patch('prepare_backup_operations.monitoring',return_value="print('monitoring reached')"):
            return combined('ops@example.com')

    def test_retention_failure_stops_without_embedded_traceback(self):
        r=subprocess.run([sys.executable,'-c',self.build("raise RuntimeError('Unexpected changes; not executed')")],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(r.stderr.strip(),'retention setup: Unexpected changes; not executed')
        self.assertNotIn('monitoring reached',r.stdout)
        self.assertNotIn('Traceback',r.stderr)

    def test_already_configured_retention_continues(self):
        r=subprocess.run([sys.executable,'-c',self.build('raise SystemExit(0)')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('monitoring reached',r.stdout)

if __name__=='__main__':unittest.main()
