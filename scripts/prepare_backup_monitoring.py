#!/usr/bin/env python3
"""Generate a small CloudFormation monitoring stack and an Admin CloudShell launcher."""
import argparse
import json
from pathlib import Path
import re


def template(email):
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Valid email required')
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Guten backup heartbeat: one metric/alarm, SNS email and scoped metric permission. No compute resources.',
        'Conditions':{'Approved':{'Fn::And':[{'Fn::Equals':[{'Ref':'AWS::AccountId'},'983732020946']},{'Fn::Equals':[{'Ref':'AWS::Region'},'us-east-1']}] }},
        'Resources':{
            'Topic':{'Type':'AWS::SNS::Topic','Condition':'Approved','Properties':{'TopicName':'guten-backup-alerts','Tags':[{'Key':'Project','Value':'Guten'}]}},
            'Subscription':{'Type':'AWS::SNS::Subscription','Condition':'Approved','Properties':{'Protocol':'email','Endpoint':email,'TopicArn':{'Ref':'Topic'}}},
            'TopicPolicy':{'Type':'AWS::SNS::TopicPolicy','Condition':'Approved','Properties':{'Topics':[{'Ref':'Topic'}],'PolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'cloudwatch.amazonaws.com'},'Action':'sns:Publish','Resource':{'Ref':'Topic'},'Condition':{'StringEquals':{'aws:SourceAccount':'983732020946'},'ArnEquals':{'aws:SourceArn':'arn:aws:cloudwatch:us-east-1:983732020946:alarm:guten-backup-health'}}}]}}},
            'MetricPermission':{'Type':'AWS::IAM::Policy','Condition':'Approved','Properties':{'PolicyName':'GutenBackupHealth','Users':['guten-backup-uploader'],'PolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':'cloudwatch:PutMetricData','Resource':'*','Condition':{'StringEquals':{'cloudwatch:namespace':'Guten/Operations'}}}]}}},
            'Alarm':{'Type':'AWS::CloudWatch::Alarm','Condition':'Approved','DependsOn':'TopicPolicy','Properties':{
                'AlarmName':'guten-backup-health','AlarmDescription':'Guten database backup unhealthy or heartbeat missing. Value bit flags: 1 failed backup; 2 no uploaded backup within 30h; 4 disk below 15% free; 8 certificate expires within 30d. SSH to database host and inspect guten-backup/guten-backup-health journals. Missing data may indicate stopped host, network or credential failure.',
                'Namespace':'Guten/Operations','MetricName':'BackupHealth','Dimensions':[{'Name':'Host','Value':'guten-db-01'}],
                'Period':900,'EvaluationPeriods':2,'DatapointsToAlarm':2,'Statistic':'Maximum','Threshold':0,'ComparisonOperator':'GreaterThanThreshold','TreatMissingData':'breaching',
                'AlarmActions':[{'Ref':'Topic'}],'OKActions':[{'Ref':'Topic'}],
            }},
        },'Outputs':{'TopicArn':{'Condition':'Approved','Value':{'Ref':'Topic'}},'AlarmName':{'Condition':'Approved','Value':{'Ref':'Alarm'}}}}


def launcher(config):
    return '''#!/usr/bin/env python3
import json,subprocess
CONFIG = '''+repr(config)+'''

def aws(*args):
    result=subprocess.run(['aws',*args,'--region','us-east-1','--output','json'],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return json.loads(result.stdout) if result.stdout.strip() else {}
identity=aws('sts','get-caller-identity')
assert identity['Account']=='983732020946' and identity['Arn']=='arn:aws:iam::983732020946:user/Admin', 'Use the expected Admin user'
r=subprocess.run(['aws','cloudformation','describe-stacks','--stack-name','guten-backup-monitoring','--region','us-east-1'],capture_output=True,text=True)
if r.returncode==0:raise RuntimeError('Monitoring stack already exists; inspect it instead of creating duplicates.')
if 'does not exist' not in r.stderr:raise RuntimeError(r.stderr)
aws('cloudformation','validate-template','--template-body',json.dumps(CONFIG))
result=aws('cloudformation','create-stack','--stack-name','guten-backup-monitoring','--template-body',json.dumps(CONFIG),'--capabilities','CAPABILITY_NAMED_IAM','--enable-termination-protection')
print(json.dumps(result))
print('Confirm the AWS SNS email subscription. Then let Codex verify the stack and activate the host heartbeat.')
'''


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--email',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as stream:stream.write(launcher(template(a.email)))
    a.output.chmod(0o700)
    print(a.output)
