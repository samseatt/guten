#!/usr/bin/env python3
"""Wrap the reviewed bootstrap template for explicit execution in Admin CloudShell."""
import argparse
import json
from pathlib import Path


def launcher(template):
    request={
        'StackName':'guten-bootstrap', 'TemplateBody':json.dumps(template),
        'EnableTerminationProtection':True,
        'Tags':[{'Key':'Project','Value':'Guten'},{'Key':'Environment','Value':'bootstrap'}],
        'StackPolicyBody':json.dumps({'Statement':[
            {'Effect':'Allow','Action':'Update:*','Principal':'*','Resource':'*'},
            {'Effect':'Deny','Action':['Update:Replace','Update:Delete'],'Principal':'*','Resource':['LogicalResourceId/DatabaseHost','LogicalResourceId/BackupBucket']},
        ]}),
    }
    return '''#!/bin/bash
# Run explicitly in AWS CloudShell as Admin, not on the Mac's audit profile.
# Creates two Lightsail hosts (USD 36/month combined), an attached static IP,
# and private S3 backup storage (usage-based). No app/database starts yet.
set -euo pipefail
export AWS_PAGER=""
region=us-east-1
account=$(aws sts get-caller-identity --query Account --output text)
if [ "$account" != 983732020946 ]; then
  echo 'Wrong AWS account; no resources created.' >&2
  exit 1
fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if aws cloudformation describe-stacks --region "$region" --stack-name guten-bootstrap >"$work/stack" 2>"$work/error"; then
  echo 'guten-bootstrap already exists. Inspect it; this launcher never updates or duplicates a stack.' >&2
  exit 1
elif ! grep -q 'does not exist' "$work/error"; then
  cat "$work/error" >&2
  exit 1
fi
instances=$(aws lightsail get-instances --region "$region" --query "length(instances[?name=='guten-app-01' || name=='guten-db-01'])" --output text)
ips=$(aws lightsail get-static-ips --region "$region" --query "length(staticIps[?name=='guten-app-ip'])" --output text)
buckets=$(aws s3api list-buckets --query "length(Buckets[?Name=='guten-backups-983732020946-us-east-1'])" --output text)
if [ "$instances" != 0 ] || [ "$ips" != 0 ] || [ "$buckets" != 0 ]; then
  echo 'A planned resource name is already in this account; refusing to create/adopt duplicates.' >&2
  exit 1
fi
aws lightsail get-bundles --region "$region" --output json > "$work/bundles.json"
python3 - "$work/bundles.json" <<'GUTEN_BUNDLE_CHECK'
import json,sys
bundles={b['bundleId']:b for b in json.load(open(sys.argv[1]))['bundles']}
for name,price,ram,disk in [('small_3_0',12,2,60),('medium_3_0',24,4,80)]:
    b=bundles.get(name,{})
    if not (b.get('isActive') and b.get('price')==price and b.get('ramSizeInGb')==ram and b.get('diskSizeInGb')==disk and 'LINUX_UNIX' in b.get('supportedPlatforms',[])):
        raise SystemExit('Bundle availability/specification/price changed; review before creating any resources.')
GUTEN_BUNDLE_CHECK
cat > "$work/template.json" <<'GUTEN_TEMPLATE_JSON'
TEMPLATE_JSON
GUTEN_TEMPLATE_JSON
cat > "$work/request.json" <<'GUTEN_REQUEST_JSON'
REQUEST_JSON
GUTEN_REQUEST_JSON
aws cloudformation validate-template --region "$region" --template-body "file://$work/template.json" --query Description --output text
aws cloudformation create-stack --region "$region" --cli-input-json "file://$work/request.json"
echo 'Creation requested. Check the guten-bootstrap CloudFormation stack in us-east-1 for CREATE_COMPLETE.'
echo 'If creation fails, inspect stack events and remaining resources; do not blindly rerun or delete a live stack.'
'''.replace('TEMPLATE_JSON\n',json.dumps(template,indent=2)+'\n',1).replace('REQUEST_JSON\n',json.dumps(request,indent=2)+'\n',1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as stream: stream.write(launcher(json.loads(a.template.read_text())))
    a.output.chmod(0o700)
    print(a.output)
