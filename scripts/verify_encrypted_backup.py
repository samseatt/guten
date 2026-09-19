#!/usr/bin/env python3
"""Restore a cloud archive into a disposable local TLS cluster and compare fingerprints."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
from fingerprint_database import fingerprint

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True,type=Path)
    p.add_argument('--identity',required=True,type=Path)
    p.add_argument('--expected',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    a=p.parse_args()
    for path in (a.archive,a.identity,a.expected):
        if not path.exists():p.error(f'Missing input: {path}')
    if a.report.exists():p.error('Report already exists')
    docker=shutil.which('docker') or '/usr/local/bin/docker'
    token=secrets.token_hex(6)
    project='guten-recovery-'+token
    volume=project+'-pg17'
    def run(command,**kwargs):
        return subprocess.run(command,check=True,text=True,capture_output=True,**kwargs).stdout.strip()
    with tempfile.TemporaryDirectory(prefix='guten-recovery-') as folder:
        config=Path(folder)/'config'
        run(['python3',str(ROOT/'scripts/configure_database.py'),'--output',str(config),'--database-ip','127.0.0.1','--app-ip','172.26.5.8','--backup-subnet','172.30.224.0/24','--test'])
        runtime=config/'runtime'
        composefile=runtime/'compose.yaml'
        conf=json.loads(composefile.read_text())
        conf['services']['postgres'].pop('ports')  # No connection to host/native database.
        composefile.write_text(json.dumps(conf))
        env=dict(os.environ,GUTEN_PG_VOLUME=volume)
        compose=[docker,'compose','-p',project,'-f',str(composefile)]
        run([docker,'volume','create',volume])
        try:
            run(compose+['up','-d','--wait','--wait-timeout','90','postgres'],env=env)
            run(compose+['run','--rm','-T','-e','PGUSER=postgres','-e','PGDATABASE=postgres','-e','PGPASSFILE=/admin_pgpass','-v',f'{runtime / "admin_pgpass"}:/admin_pgpass:ro','-v',f'{a.archive.resolve()}:/archive:ro','-v',f'{a.identity.resolve()}:/identity:ro','backup','restore','--archive','/archive','--identity','/identity','--target','guten_restore_verified'],env=env)
            container=run(compose+['ps','-q','postgres'],env=env)
            restored=fingerprint([docker,'exec','-u','postgres',container,'psql'],'guten_restore_verified')
            expected=json.loads(a.expected.read_text())
            if restored!=expected:
                raise RuntimeError('Recovery fingerprint differs from expected cloud content/schema')
            report={'passed':True,'archive':str(a.archive.resolve()),'manifest':json.loads((a.archive/'manifest.json').read_text()),'tables':len(restored['tables']),'sequences':len(restored['sequences']),'columns':len(restored['columns']),'indexes':len(restored['indexes'])}
        finally:
            run(compose+['down','--remove-orphans'],env=env)
            run([docker,'volume','rm',volume])
        report['disposable_cluster_removed']=True
        a.report.parent.mkdir(parents=True,exist_ok=True)
        with a.report.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        print('Encrypted recovery passed; exact content/schema match; disposable cluster removed.')

if __name__=='__main__':main()
