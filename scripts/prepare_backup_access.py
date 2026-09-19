#!/usr/bin/env python3
"""Generate a reviewable Admin CloudShell script; credentials are RSA-encrypted for the Mac."""
import argparse
import json
from pathlib import Path
import subprocess

BUCKET='guten-backups-983732020946-us-east-1'
PREFIX='guten/database/'
USER='guten-backup-uploader'


def policies():
    resource=f'arn:aws:s3:::{BUCKET}'
    upload={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':['s3:PutObject','s3:AbortMultipartUpload','s3:ListMultipartUploadParts'],'Resource':resource+'/'+PREFIX+'*','Condition':{'Bool':{'aws:SecureTransport':'true'}}}]}
    audit={'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Action':['s3:GetBucketPublicAccessBlock','s3:GetEncryptionConfiguration','s3:GetBucketVersioning','s3:GetBucketPolicy','s3:GetLifecycleConfiguration'],'Resource':resource},
        {'Effect':'Allow','Action':'s3:ListBucket','Resource':resource,'Condition':{'StringLike':{'s3:prefix':[PREFIX,PREFIX+'*']}}},
        {'Effect':'Allow','Action':['s3:GetObject','s3:GetObjectVersion'],'Resource':resource+'/'+PREFIX+'*'},
    ]}
    return upload,audit


def launcher(public_pem):
    upload,audit=policies()
    values=repr({'public_key':public_pem,'upload':upload,'audit':audit,'bucket':BUCKET,'user':USER})
    return '''#!/usr/bin/env python3
# Run in Admin CloudShell. No secret is printed or written as plaintext.
import json,subprocess,tempfile
from pathlib import Path
CONFIG = '''+values+'''

def aws(*args):
    r=subprocess.run(['aws',*args,'--region','us-east-1','--output','json'],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout) if r.stdout.strip() else {}

identity=aws('sts','get-caller-identity')
assert identity['Account']=='983732020946' and identity['Arn']=='arn:aws:iam::983732020946:user/Admin', 'Use this account’s Admin user in CloudShell.'
output=Path.home()/'guten-backup-credentials.enc'
assert not output.exists(), 'Encrypted credentials already exist; do not create another key.'
# Fail on any error except the expected absent user.
r=subprocess.run(['aws','iam','get-user','--user-name',CONFIG['user'],'--output','json'],capture_output=True,text=True)
if r.returncode==0: raise RuntimeError('Uploader user already exists. Inspect its policy/keys; do not create duplicates.')
if 'NoSuchEntity' not in r.stderr: raise RuntimeError(r.stderr)
block=aws('s3api','get-public-access-block','--bucket',CONFIG['bucket'])['PublicAccessBlockConfiguration']
assert all(block.get(k) is True for k in ['BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'])
assert aws('s3api','get-bucket-versioning','--bucket',CONFIG['bucket']).get('Status')=='Enabled'
encryption=aws('s3api','get-bucket-encryption','--bucket',CONFIG['bucket'])
assert encryption['ServerSideEncryptionConfiguration']['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']=='AES256'
aws('iam','put-role-policy','--role-name','GutenAudit','--policy-name','GutenBackupRecovery','--policy-document',json.dumps(CONFIG['audit']))
aws('iam','create-user','--user-name',CONFIG['user'],'--tags','Key=Project,Value=Guten','Key=Purpose,Value=DatabaseBackup')
aws('iam','put-user-policy','--user-name',CONFIG['user'],'--policy-name','GutenBackupUpload','--policy-document',json.dumps(CONFIG['upload']))
# Failures after user creation deliberately stop; recover that same user, never create extras.
key=aws('iam','create-access-key','--user-name',CONFIG['user'])['AccessKey']
credentials='[default]\\naws_access_key_id = '+key['AccessKeyId']+'\\naws_secret_access_key = '+key['SecretAccessKey']+'\\n'
with tempfile.TemporaryDirectory() as folder:
    public=Path(folder)/'public.pem'
    public.write_text(CONFIG['public_key'])
    encrypted=subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(public),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],input=credentials.encode(),capture_output=True,check=True).stdout
    with output.open('xb') as stream:stream.write(encrypted)
    output.chmod(0o600)
print('Created upload-only identity and scoped audit recovery access. No console login was created.')
print('Download this encrypted file using CloudShell Actions > Download file: '+str(output))
print('It can only be decrypted with the Guten SSH private key on your Mac. Do not paste secrets in chat.')
'''


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public-key',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    public=subprocess.check_output(['ssh-keygen','-e','-m','PKCS8','-f',str(a.public_key)],text=True)
    with a.output.open('x') as stream:stream.write(launcher(public))
    a.output.chmod(0o700)
    print(a.output)
