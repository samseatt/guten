#!/usr/bin/env python3
"""Inspect local upload receipts and host health; optionally emit one CloudWatch metric."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

PREFIX='s3://guten-backups-983732020946-us-east-1/guten/database/'
COMPOSE=['docker','compose','--env-file','/etc/guten/database.env','-f','/etc/guten/database/compose.yaml','-f','/etc/guten/database/compose.upload.yaml']


def uploaded(root):
    found=[]
    for path in root.glob('guten_*'):
        if path.is_symlink() or not path.is_dir(): continue
        try:
            names={'full.dump.age','manifest.json','UPLOADED'}
            if set(p.name for p in path.iterdir())!=names: continue
            if any((path/n).is_symlink() or not (path/n).is_file() for n in names): continue
            meta=json.loads((path/'manifest.json').read_text())
            if meta.get('format')!=1 or meta.get('database')!='guten_datalake': continue
            if not re.fullmatch('[a-f0-9]{64}',meta.get('sha256','')): continue
            if (path/'UPLOADED').read_text().strip()!=PREFIX+path.name+'/': continue
            created=datetime.fromisoformat(meta['created_utc'])
            if created.tzinfo is None or (path/'full.dump.age').stat().st_size==0: continue
            found.append((created,path,meta))
        except (OSError,ValueError,KeyError,TypeError): continue
    return sorted(found,key=lambda item:item[0],reverse=True)


def evaluate(now,archives,result,free_fraction,certificate_ok):
    reasons=[];code=0
    if result!='success':code|=1;reasons.append('backup service failed or status unavailable')
    if not archives or not 0 <= (now-archives[0][0]).total_seconds() <= 30*3600:
        code|=2;reasons.append('no verified upload receipt within 30 hours')
    if free_fraction<.15:code|=4;reasons.append('less than 15 percent free disk space')
    if not certificate_ok:code|=8;reasons.append('database certificate expires within 30 days or is unreadable')
    return {'code':code,'reasons':reasons,'latest_upload':archives[0][0].isoformat() if archives else None,'free_disk_percent':round(free_fraction*100,2)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publish',action='store_true')
    a=p.parse_args()
    root=Path('/etc/guten/database/backups')
    result=subprocess.run(['systemctl','show','guten-backup.service','--property=Result','--value'],capture_output=True,text=True)
    cert=subprocess.run(['openssl','x509','-checkend','2592000','-noout','-in','/etc/guten/database/server.crt'],capture_output=True)
    usage=shutil.disk_usage(root)
    health=evaluate(datetime.now(timezone.utc),uploaded(root),result.stdout.strip() if result.returncode==0 else 'unknown',usage.free/usage.total,cert.returncode==0)
    print(json.dumps(health),flush=True)
    if a.publish:
        metric=[{'MetricName':'BackupHealth','Dimensions':[{'Name':'Host','Value':'guten-db-01'}],'Value':health['code'],'Unit':'None'}]
        subprocess.run(COMPOSE+['run','--rm','-T','--no-deps','--entrypoint','aws','backup','cloudwatch','put-metric-data','--region','us-east-1','--namespace','Guten/Operations','--metric-data',json.dumps(metric),'--cli-connect-timeout','5','--cli-read-timeout','10'],check=True,timeout=120)

if __name__=='__main__':main()
