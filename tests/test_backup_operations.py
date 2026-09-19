import hashlib
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy/database'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from backup_health import uploaded,evaluate,PREFIX
from prune_backups import prune
from prepare_backup_monitoring import template
from prepare_backup_retention import rules


class OperationsTests(unittest.TestCase):
    def make_archive(self,root,name,created,receipt=True):
        path=root/name;path.mkdir()
        (path/'full.dump.age').write_bytes(b'ciphertext')
        (path/'manifest.json').write_text(json.dumps({'format':1,'database':'guten_datalake','created_utc':created.isoformat(),'sha256':hashlib.sha256(b'ciphertext').hexdigest()}))
        if receipt:(path/'UPLOADED').write_text(PREFIX+name+'/\n')
        return path

    def test_retention_keeps_seven_and_failed_and_checks_ciphertext(self):
        now=datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for i in range(11):self.make_archive(root,f'guten_{i:02}',now-timedelta(days=0 if i==0 else 40+i))
            failed=self.make_archive(root,'guten_failed',now-timedelta(days=100),False)
            (root/'guten_09'/'full.dump.age').write_bytes(b'damaged')
            selected=prune(root,now)
            self.assertEqual(set(selected),{'guten_07','guten_08','guten_10'})
            self.assertEqual(len(list(root.iterdir())),12)
            self.assertEqual(set(prune(root,now,True)),set(selected))
            self.assertTrue(failed.exists());self.assertTrue((root/'guten_09').exists())
            self.assertEqual(len(uploaded(root)),8)

    def test_stale_uploads_and_symlinks_prevent_deletion(self):
        now=datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for i in range(9):self.make_archive(root,f'guten_{i}',now-timedelta(days=90+i))
            self.assertEqual(prune(root,now,True),[])
            external=root/'external';external.write_text('important')
            (root/'guten_0'/'UPLOADED').unlink();(root/'guten_0'/'UPLOADED').symlink_to(external)
            self.assertEqual(len(uploaded(root)),8)
            self.assertEqual(external.read_text(),'important')

    def test_health_codes(self):
        now=datetime.now(timezone.utc)
        archives=[(now,Path('/unused'),{})]
        self.assertEqual(evaluate(now,archives,'success',.5,True)['code'],0)
        self.assertEqual(evaluate(now,archives,'failed',.5,True)['code'],1)
        self.assertEqual(evaluate(now,[],'success',.5,True)['code'],2)
        self.assertEqual(evaluate(now,archives,'success',.14,True)['code'],4)
        self.assertEqual(evaluate(now,archives,'success',.5,False)['code'],8)
        self.assertEqual(evaluate(now,[],'failed',.14,False)['code'],15)

    def test_small_monitoring_scope_and_missing_data_alarm(self):
        resources=template('ops@example.com')['Resources']
        self.assertEqual(len(resources),5)
        alarm=resources['Alarm']['Properties']
        self.assertEqual(alarm['TreatMissingData'],'breaching')
        self.assertEqual(alarm['Period'],900)
        policy=resources['MetricPermission']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(policy['Action'],'cloudwatch:PutMetricData')
        self.assertEqual(policy['Condition']['StringEquals']['cloudwatch:namespace'],'Guten/Operations')
        self.assertTrue(all(r['Type'] in {'AWS::SNS::Topic','AWS::SNS::TopicPolicy','AWS::SNS::Subscription','AWS::IAM::Policy','AWS::CloudWatch::Alarm'} for r in resources.values()))
        self.assertEqual(rules()[0]['Prefix'],'guten/database/')
        self.assertEqual(rules()[0]['ExpirationInDays'],180)
        self.assertEqual(rules()[0]['NoncurrentVersionExpiration']['NoncurrentDays'],30)

if __name__=='__main__':unittest.main()
