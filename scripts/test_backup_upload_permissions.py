#!/usr/bin/env python3
"""Run on the database host: check upload identity and deny read/delete boundaries."""
import argparse
import json
import subprocess
import uuid

BUCKET='guten-backups-983732020946-us-east-1'
COMPOSE=['docker','compose','--env-file','/etc/guten/database.env','-f','/etc/guten/database/compose.yaml','-f','/etc/guten/database/compose.upload.yaml','run','--rm','-T','--no-deps','--entrypoint','aws','backup']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive-key',required=True,help='Existing guten/database/.../full.dump.age key')
    a=p.parse_args()
    if not a.archive_key.startswith('guten/database/') or not a.archive_key.endswith('/full.dump.age'):
        p.error('Expected a Guten backup ciphertext key')
    r=subprocess.run(COMPOSE+['sts','get-caller-identity'],capture_output=True,text=True,check=True)
    assert json.loads(r.stdout)['Arn']=='arn:aws:iam::983732020946:user/guten-backup-uploader'
    # Never attempt deletion of an archive: use a fresh random nonexistent name.
    absent='guten/database/_permission_probe_'+uuid.uuid4().hex
    checks=[
        ('object read',['s3api','get-object','--bucket',BUCKET,'--key',a.archive_key,'/tmp/permission-probe']),
        ('object deletion (random nonexistent key)',['s3api','delete-object','--bucket',BUCKET,'--key',absent]),
        ('bucket listing',['s3api','list-objects-v2','--bucket',BUCKET,'--prefix','guten/database/','--max-keys','1']),
    ]
    for label,args in checks:
        r=subprocess.run(COMPOSE+args,capture_output=True,text=True)
        if r.returncode==0 or 'AccessDenied' not in r.stderr:
            raise RuntimeError(f'Unexpected permission result for {label}; inspect identity/policy. Probe key: {absent}')
        print(label+': AccessDenied as expected')

if __name__=='__main__':main()
