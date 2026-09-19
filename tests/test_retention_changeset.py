import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_backup_retention import launcher


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
 c={'LogicalResourceId':'ApplicationHost' if mode=='host' else 'BackupBucket','Action':'Modify','Replacement':'True' if mode=='replace' else 'False','Details':[{'Target':{'Name':'BucketName' if mode=='property' else 'LifecycleConfiguration'}}]}
 print(json.dumps({'Changes':[{'ResourceChange':c}]* (2 if mode=='extra' else 1)}))
elif op==['cloudformation','execute-change-set']: Path(os.environ['CAPTURE']).touch();print('{}')
elif op==['cloudformation','wait']: pass
else: sys.exit('Unexpected call')
''')
            fake.chmod(0o700);script.write_text(launcher())
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],CAPTURE=str(capture))
            for mode in ('host','replace','property','extra'):
                r=subprocess.run([sys.executable,str(script)],env=dict(env,CASE=mode),capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0);self.assertFalse(capture.exists())
            r=subprocess.run([sys.executable,str(script)],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(capture.exists())

if __name__=='__main__':unittest.main()
