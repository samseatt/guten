import json
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_backup_retention import launcher, validate_changes


class ChangeSetTests(unittest.TestCase):
    def test_bucket_only_change_and_refusal_of_host_or_replacement_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fake=root/'aws';script=root/'setup.py';capture=root/'executed'
            fake.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
a=sys.argv[1:];op=a[:2]
if op==['sts','get-caller-identity']: print('{"Account":"983732020946","Arn":"arn:aws:iam::983732020946:user/Admin"}')
elif op==['cloudformation','describe-stacks']: print('{"Stacks":[{"StackStatus":"CREATE_COMPLETE","Parameters":[{"ParameterKey":"SshPublicKey","ParameterValue":"retained"}]}]}')
elif op==['cloudformation','get-template']: print(json.dumps({'TemplateBody':{'Resources':{'BackupBucket':{'Type':'AWS::S3::Bucket','Properties':{'BucketName':'guten-backups-983732020946-us-east-1','LifecycleConfiguration':{'Rules':[{'Id':'ExistingRule'}]}}},'ApplicationHost':{'unchanged':True}}}}))
elif op==['cloudformation','create-change-set']:
 t=json.loads(a[a.index('--template-body')+1]);assert t['Resources']['ApplicationHost']=={'unchanged':True}
 assert t['Resources']['BackupBucket']['Properties']['LifecycleConfiguration']['Rules'][0]=={'Id':'ExistingRule'}
 assert json.loads(a[a.index('--parameters')+1])==[{'ParameterKey':'SshPublicKey','UsePreviousValue':True}]
 print('{}')
elif op==['cloudformation','describe-change-set']:
 mode=os.environ.get('CASE','ok')
 changes=json.loads(Path(os.environ['FIXTURE']).read_text())
 c=changes[1]['ResourceChange']
 if mode=='host':c['LogicalResourceId']='ApplicationHost'
 if mode=='replace':c['Replacement']='True'
 if mode=='property':c['Details'][0]['Target']['Name']='BucketName'
 if mode=='extra':changes.append(changes[1])
 if mode=='ok':changes=changes[1:]
 print(json.dumps({'Changes':changes}))
elif op==['cloudformation','execute-change-set']: Path(os.environ['CAPTURE']).touch();print('{}')
elif op==['cloudformation','wait']: pass
else: sys.exit('Unexpected call')
''')
            fake.chmod(0o700);script.write_text(launcher())
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],CAPTURE=str(capture),FIXTURE=str(Path(__file__).resolve().parent/'fixtures/retention-arn-dependency.json'))
            for mode in ('host','replace','property','extra'):
                r=subprocess.run([sys.executable,str(script)],env=dict(env,CASE=mode),capture_output=True,text=True,cwd=root)
                self.assertNotEqual(r.returncode,0);self.assertFalse(capture.exists())
            for mode in ('ok','dependency'):
                r=subprocess.run([sys.executable,str(script)],env=dict(env,CASE=mode),capture_output=True,text=True,cwd=root)
                self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(capture.exists())
                capture.unlink()
            for report in root.glob('*-changes.json'):json.loads(report.read_text())

    def test_policy_exception_rejects_direct_edits_and_other_dependencies(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/retention-arn-dependency.json').read_text())
        validate_changes(fixture)
        for field,value in [('Evaluation','Static'),('ChangeSource','DirectModification'),('CausingEntity','ApplicationHost.Arn')]:
            changed=copy.deepcopy(fixture)
            changed[0]['ResourceChange']['Details'][0][field]=value
            with self.assertRaises(ValueError):validate_changes(changed)
        for field,value in [('Replacement','Conditional'),('Action','Remove'),('Scope',['Metadata']),('ResourceType','AWS::IAM::Policy')]:
            changed=copy.deepcopy(fixture);changed[0]['ResourceChange'][field]=value
            with self.assertRaises(ValueError):validate_changes(changed)
        changed=copy.deepcopy(fixture)
        changed[0]['ResourceChange']['Details'][0]['Target']['RequiresRecreation']='Conditionally'
        with self.assertRaises(ValueError):validate_changes(changed)
        with self.assertRaises(ValueError):validate_changes(fixture[:1])


if __name__=='__main__':unittest.main()
