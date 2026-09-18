#!/usr/bin/env python3
"""Read-only Guten AWS inventory. No Cost Explorer calls or resource mutations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

ACCOUNT='983732020946'
PROFILE='guten-audit'
REGION='us-east-1'
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,help='New JSON report; defaults to ignored artifacts/.')
    a=p.parse_args()
    os.umask(0o077)
    aws=shutil.which('aws') or str(Path.home()/'.local/bin/aws')
    def read(args,query=None):
        command=[aws,*args,'--profile',PROFILE,'--region',REGION,'--output','json','--no-cli-pager','--cli-connect-timeout','10','--cli-read-timeout','30']
        if query: command+=['--query',query]
        result=subprocess.run(command,capture_output=True,text=True,timeout=90)
        if result.returncode: return {'error':result.stderr.strip()}
        return {'data':json.loads(result.stdout)}
    identity=read(['sts','get-caller-identity'])
    if 'error' in identity: raise SystemExit(identity['error'])
    who=identity['data']
    if who.get('Account')!=ACCOUNT or not who.get('Arn','').startswith(f'arn:aws:sts::{ACCOUNT}:assumed-role/GutenAudit/'):
        raise SystemExit('Refusing inventory outside the expected account and GutenAudit role.')
    checks={
        'lightsail_regions':(['lightsail','get-regions','--include-availability-zones'],"regions[?name=='us-east-1'].{name:name,zones:availabilityZones}"),
        'lightsail_quotas':(['service-quotas','list-service-quotas','--service-code','lightsail'],'Quotas[].{name:QuotaName,value:Value,code:QuotaCode}'),
        'lightsail_instances':(['lightsail','get-instances'],'instances[].{name:name,state:state.name,bundle:bundleId,blueprint:blueprintId,zone:location.availabilityZone,staticIP:isStaticIp,tags:tags}'),
        'lightsail_bundles':(['lightsail','get-bundles'],'bundles[?isActive && (ramSizeInGb==`2` || ramSizeInGb==`4`)].{id:bundleId,price:price,ram:ramSizeInGb,disk:diskSizeInGb,transfer:transferPerMonthInGb,platforms:supportedPlatforms,ipType:publicIpv4AddressCount}'),
        'lightsail_blueprints':(['lightsail','get-blueprints'],'blueprints[?isActive && type==`os`].{id:blueprintId,name:name,version:version,platform:platform}'),
        'lightsail_static_ips':(['lightsail','get-static-ips'],'staticIps[].{name:name,attached:isAttached,instance:attachedTo}'),
        'lightsail_snapshots':(['lightsail','get-instance-snapshots'],'instanceSnapshots[].{name:name,created:createdAt,state:state,source:fromInstanceName,size:sizeInGb}'),
        's3_buckets':(['s3api','list-buckets'],'Buckets[].{name:Name,created:CreationDate}'),
        'ec2_instances':(['ec2','describe-instances'],'Reservations[].Instances[].{id:InstanceId,type:InstanceType,state:State.Name,zone:Placement.AvailabilityZone}'),
        'ebs_volumes':(['ec2','describe-volumes'],'Volumes[].{id:VolumeId,gb:Size,type:VolumeType,state:State}'),
        'ec2_addresses':(['ec2','describe-addresses'],'Addresses[].{allocation:AllocationId,instance:InstanceId,association:AssociationId}'),
        'budgets':(['budgets','describe-budgets','--account-id',ACCOUNT],'Budgets[].{name:BudgetName,type:BudgetType,limit:BudgetLimit,actual:CalculatedSpend.ActualSpend,filters:CostFilters}'),
    }
    report={'checked_utc':datetime.now(timezone.utc).isoformat(),'identity':who,'region':REGION,'scope':'Virginia resources plus global S3 bucket names and budgets; not an all-region billing audit.','checks':{}}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={name:pool.submit(read,args,query) for name,(args,query) in checks.items()}
        for name,future in futures.items():
            try: report['checks'][name]=future.result()
            except Exception as error: report['checks'][name]={'error':str(error)}
            print(name+': '+('unavailable' if 'error' in report['checks'][name] else 'read successfully'))
    output=a.output or ROOT/'artifacts'/('aws_audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream: json.dump(report,stream,indent=2); stream.write('\n')
    print('Report:',output)


if __name__=='__main__': main()
