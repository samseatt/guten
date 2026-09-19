#!/usr/bin/env python3
"""Prepare a bucket-only CloudFormation retention update, preserving host resources."""
import argparse
import inspect
from pathlib import Path


def rules():
    return [
        {'Id':'GutenDatabaseRetention','Status':'Enabled','Prefix':'guten/database/','ExpirationInDays':180,'NoncurrentVersionExpiration':{'NoncurrentDays':30}},
        {'Id':'GutenDatabaseDeleteMarkers','Status':'Enabled','Prefix':'guten/database/','ExpiredObjectDeleteMarker':True},
    ]



def validate_changes(changes):
    """Allow only lifecycle plus its observed unchanged-policy ARN dependency."""
    seen=set()
    for change in changes:
        r=change.get('ResourceChange',{})
        name=r.get('LogicalResourceId')
        if change.get('Type')!='Resource' or name in seen or name not in {'BackupBucket','BackupBucketPolicy'}:
            raise ValueError('Unexpected/duplicate resource change; NOT executed')
        seen.add(name)
        expected_type='AWS::S3::Bucket' if name=='BackupBucket' else 'AWS::S3::BucketPolicy'
        if r.get('Action')!='Modify' or r.get('Replacement')!='False' or r.get('ResourceType')!=expected_type or r.get('Scope')!=['Properties']:
            raise ValueError('Unexpected action, type, scope or replacement; NOT executed')
        details=r.get('Details',[])
        if len(details)!=1:
            raise ValueError('Unexpected change details; NOT executed')
        d=details[0]
        target=d.get('Target',{})
        property_name='LifecycleConfiguration' if name=='BackupBucket' else 'PolicyDocument'
        if target.get('Attribute')!='Properties' or target.get('Name')!=property_name or target.get('RequiresRecreation')!='Never':
            raise ValueError('Unexpected property change; NOT executed')
        if name=='BackupBucket':
            if d.get('Evaluation')!='Static' or d.get('ChangeSource')!='DirectModification' or d.get('CausingEntity'):
                raise ValueError('Unexpected lifecycle change source; NOT executed')
        elif d.get('Evaluation')!='Dynamic' or d.get('ChangeSource')!='ResourceAttribute' or d.get('CausingEntity')!='BackupBucket.Arn':
            raise ValueError('Policy edit is not the known bucket ARN dependency; NOT executed')
    if 'BackupBucket' not in seen:
        raise ValueError('Lifecycle change missing; NOT executed')


def launcher():
    return '''#!/usr/bin/env python3
import copy,json,subprocess,uuid
from pathlib import Path
RETENTION = '''+repr(rules())+'\n'+inspect.getsource(validate_changes)+'''

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
report=Path(name+'-changes.json')
report.write_text(json.dumps(change,indent=2)+chr(10))
print('Change-set details saved to '+str(report),flush=True)
print(json.dumps([{'resource':c['ResourceChange']['LogicalResourceId'],'action':c['ResourceChange']['Action'],'replacement':c['ResourceChange'].get('Replacement')} for c in changes],indent=2),flush=True)
validate_changes(changes)
print('Verified nonreplacement lifecycle update and any unchanged-policy ARN dependency. Executing approved retention.')
aws('cloudformation','execute-change-set','--stack-name','guten-bootstrap','--change-set-name',name)
aws('cloudformation','wait','stack-update-complete','--stack-name','guten-bootstrap')
print('Retention update complete. No host or database volume replacement was requested.')
'''


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as stream:stream.write(launcher())
