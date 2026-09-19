import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import serialization,hashes
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_backup_access import launcher,policies


class BackupAccessTests(unittest.TestCase):
    def test_policies_have_no_delete_or_uploader_read_access(self):
        upload,audit=policies()
        self.assertEqual(set(upload['Statement'][0]['Action']),{'s3:PutObject','s3:AbortMultipartUpload','s3:ListMultipartUploadParts'})
        self.assertTrue(upload['Statement'][0]['Resource'].endswith('/guten/database/*'))
        self.assertNotIn('Delete',json.dumps(audit))
        self.assertNotIn('PutObject',json.dumps(audit))

    def test_launcher_guards_and_encrypted_handoff(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            fake=root/'aws'
            fake.write_text('''#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
args=sys.argv[1:]
if args[:2]==['sts','get-caller-identity']:
 print(json.dumps({'Account':os.environ.get('TEST_ACCOUNT','983732020946'),'Arn':'arn:aws:iam::983732020946:user/Admin'}))
elif args[:2]==['iam','get-user']:
 if os.environ.get('TEST_EXISTS'): print('{}')
 else: print('NoSuchEntity',file=sys.stderr);sys.exit(1)
elif args[:2]==['s3api','get-public-access-block']: print(json.dumps({'PublicAccessBlockConfiguration':{k:not bool(os.environ.get('TEST_PUBLIC')) for k in ['BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets']}}))
elif args[:2]==['s3api','get-bucket-versioning']: print('{"Status":"Enabled"}')
elif args[:2]==['s3api','get-bucket-encryption']: print('{"ServerSideEncryptionConfiguration":{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}}')
elif args[:2]==['iam','create-access-key']: print('{"AccessKey":{"AccessKeyId":"TESTKEY","SecretAccessKey":"TESTSECRET"}}')
elif args[0]=='iam':
 with Path(os.environ['TEST_CALLS']).open('a') as f: f.write(json.dumps(args)+'\\n')
 print('{}')
else: sys.exit('Unexpected command')
''')
            fake.chmod(0o700)
            output=root/'guten-backup-credentials.enc'
            script=root/'setup.py'
            script.write_text(launcher(public).replace("Path.home()/'guten-backup-credentials.enc'",repr(str(output))).replace('output='+repr(str(output)), 'output=Path('+repr(str(output))+')'))
            calls=root/'calls'
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],TEST_CALLS=str(calls))
            for extra in [{'TEST_ACCOUNT':'000000000000'},{'TEST_EXISTS':'yes'},{'TEST_PUBLIC':'yes'}]:
                result=subprocess.run([sys.executable,str(script)],env=dict(env,**extra),capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(output.exists())
                self.assertFalse(calls.exists())
            result=subprocess.run([sys.executable,str(script)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('TESTSECRET',result.stdout+result.stderr)
            clear=key.decrypt(output.read_bytes(),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            self.assertIn(b'aws_secret_access_key = TESTSECRET',clear)
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            private=root/'private.pem'
            private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            private.chmod(0o600)
            destination=root/'backup_aws'
            helper=Path(__file__).resolve().parents[1]/'scripts/decrypt_backup_credentials.py'
            decoded=subprocess.run([sys.executable,str(helper),'--input',str(output),'--private-key',str(private),'--output',str(destination)],capture_output=True,text=True)
            self.assertEqual(decoded.returncode,0,decoded.stderr)
            self.assertEqual(destination.read_bytes(),clear)
            self.assertEqual(destination.stat().st_mode & 0o777,0o600)
            self.assertNotIn('TESTSECRET',decoded.stdout+decoded.stderr)
            result=subprocess.run([sys.executable,str(script)],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)

if __name__=='__main__':unittest.main()
