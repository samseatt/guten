#!/usr/bin/env python3
"""Prepare a bucket-only CloudFormation retention update, preserving host resources."""
import argparse
from pathlib import Path


def rules():
    return [
        {'Id':'GutenDatabaseRetention','Status':'Enabled','Prefix':'guten/database/','ExpirationInDays':180,'NoncurrentVersionExpiration':{'NoncurrentDays':30}},
        {'Id':'GutenDatabaseDeleteMarkers','Status':'Enabled','Prefix':'guten/database/','ExpiredObjectDeleteMarker':True},
    ]


def launcher():
    return '''#!/usr/bin/env python3
import copy,json,subprocess,uuid
RETENTION = '''+repr(rules())+'''

def aws(*args):
    r=subprocess.run(['aws',*args,'--region','us-east-1','--output','json'],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return json.loads(r.stdout) if r.stdout.strip() else {}
identity=aws('sts','get-caller-identity')
assert identity['Account']=='983732020946' and identity['Arn']=='arn:aws:iam::983732020946:user/Admin', 'Use the expected Admin user'
stack=aws('cloudformation','describe-stacks','--stack-name','guten-bootstrap')['Stacks'][0]
assert stack['StackStatus'] in ['CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE'], 'Stack is not stable'
original=aws('cloudformation','get-template','--stack-name','guten-bootstrap','--template-stage','Original')['TemplateBody']
if isinstance(original,str):original=json.loads(original)
updated=copy.deepcopy(original)
bucket=updated['Resources']['BackupBucket']
assert bucket['Type']=='AWS::S3::Bucket' and bucket['Properties']['BucketName']=='guten-backups-983732020946-us-east-1'
existing=bucket['Properties']['LifecycleConfiguration']['Rules']
ids={r['Id'] for r in RETENTION}
kept=[r for r in existing if r.get('Id') not in ids]
bucket['Properties']['LifecycleConfiguration']['Rules']=kept+RETENTION
if original==updated:
    print('Approved retention already configured; no update required.');raise SystemExit(0)
# Only a bucket lifecycle edit is allowed in the generated template.
check=copy.deepcopy(updated)
check['Resources']['BackupBucket']['Properties']['LifecycleConfiguration']=original['Resources']['BackupBucket']['Properties']['LifecycleConfiguration']
assert check==original
name='guten-retention-'+uuid.uuid4().hex[:10]
aws('cloudformation','create-change-set','--stack-name','guten-bootstrap','--change-set-name',name,'--change-set-type','UPDATE','--template-body',json.dumps(updated),'--parameters',json.dumps([{'ParameterKey':p['ParameterKey'],'UsePreviousValue':True} for p in stack.get('Parameters',[])]))
aws('cloudformation','wait','change-set-create-complete','--stack-name','guten-bootstrap','--change-set-name',name)
change=aws('cloudformation','describe-change-set','--stack-name','guten-bootstrap','--change-set-name',name)
changes=change['Changes']
assert len(changes)==1, 'Unexpected additional resource changes; change set NOT executed'
r=changes[0]['ResourceChange']
assert r['LogicalResourceId']=='BackupBucket' and r['Action']=='Modify' and r['Replacement']=='False', 'Unexpected replacement/change; NOT executed'
assert r.get('Details') and all(d['Target'].get('Name')=='LifecycleConfiguration' for d in r['Details']), 'Unexpected property change; NOT executed'
print('Verified bucket-only, nonreplacement lifecycle change. Executing approved 180+30-day retention.')
aws('cloudformation','execute-change-set','--stack-name','guten-bootstrap','--change-set-name',name)
aws('cloudformation','wait','stack-update-complete','--stack-name','guten-bootstrap')
print('Retention update complete. No host or database volume replacement was requested.')
'''


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as stream:stream.write(launcher())
