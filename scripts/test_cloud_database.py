#!/usr/bin/env python3
"""Disposable TLS/backup/restore integration test; never connects to native PostgreSQL."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DOCKER = shutil.which('docker') or '/usr/local/bin/docker'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datalake-image', default='guten-datalake:local')
    args = parser.parse_args()
    os.umask(0o077)
    token = secrets.token_hex(5)
    project = 'guten-db-test-' + token
    volume = project + '-pg17'
    artifact = ROOT / 'artifacts' / ('database_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + token)
    artifact.mkdir(parents=True)
    results = []
    def run(command, *, data=None, fails=False):
        result = subprocess.run(command, input=data, text=True, capture_output=True)
        if (result.returncode == 0) == fails:
            raise RuntimeError(f'Unexpected command status {result.returncode}: {command[0:4]}\n{result.stderr[-3000:]}')
        return result.stdout.strip()
    def passed(name):
        results.append(name)
        print('PASS:', name, flush=True)
    with tempfile.TemporaryDirectory(prefix='guten-cloud-test-') as directory:
        temp = Path(directory)
        config = temp / 'config'
        segment = 100 + secrets.randbelow(100)
        backup_subnet = f'172.28.{segment}.0/24'
        app_subnet = f'172.27.{segment}.0/24'
        app_ip = f'172.27.{segment}.10'
        run(['python3', str(ROOT/'scripts/configure_database.py'), '--output',str(config),'--database-ip','127.0.0.1','--app-ip',app_ip,'--backup-subnet',backup_subnet,'--port','17432','--test'])
        runtime = config/'runtime'
        override = temp/'override.json'
        override.write_text(json.dumps({'services':{'postgres':{'ports':['127.0.0.1::5432'],'networks':{'default':{},'app':{'aliases':['wrong-host']}}}},'networks':{'app':{'ipam':{'config':[{'subnet':app_subnet}]}}}}))
        # Replace rather than merge the published ports so parallel tests have no fixed port.
        conf = json.loads((runtime/'compose.yaml').read_text())
        conf['services']['postgres']['ports'] = ['127.0.0.1::5432']
        (runtime/'compose.yaml').write_text(json.dumps(conf))
        os.environ['GUTEN_PG_VOLUME'] = volume
        compose = [DOCKER,'compose','-p',project,'-f',str(runtime/'compose.yaml'),'-f',str(override)]
        def sql(statement, db='guten_datalake'):
            return run(compose+['exec','-T','--user','postgres','postgres','psql','-X','-v','ON_ERROR_STOP=1','-At','-d',db],data=statement)
        def client(extra, *, fails=False, data=None):
            return run(compose+['run','--rm','-T','--entrypoint','psql',*extra,'backup','-X','-v','ON_ERROR_STOP=1','-At','-c','SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()'],fails=fails,data=data)
        try:
            run([DOCKER,'volume','create',volume])
            run(compose+['up','-d','--wait','--wait-timeout','90','postgres'])
            sql('CREATE DATABASE guten_datalake;', 'postgres')
            sql("CREATE SCHEMA draft; CREATE SCHEMA published; CREATE SCHEMA workflow; CREATE TABLE draft.pages(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, text text NOT NULL); INSERT INTO draft.pages(text) VALUES ('Hello'),('café — 你好'); CREATE TABLE published.pages AS TABLE draft.pages;")
            sql((runtime/'bootstrap-roles.sql').read_text())
            assert client([]) == 't'
            passed('verified TLS backup connection')
            client(['-e','PGSSLMODE=disable'],fails=True)
            passed('unencrypted connection rejected')
            client(['-e','PGHOST=wrong-host'],fails=True)
            passed('wrong server hostname rejected')
            # Separate self-signed CA is deliberately untrusted by the server certificate.
            wrongca=temp/'wrong.crt'
            run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=Wrong CA','-keyout',str(temp/'wrong.key'),'-out',str(wrongca)])
            client(['-v',f'{wrongca}:/wrong.crt:ro','-e','PGSSLROOTCERT=/wrong.crt'],fails=True)
            passed('wrong CA rejected')
            # Exercise the actual Datalake SQLAlchemy/asyncpg configuration, not only libpq.
            url=temp/'database_url'
            url.write_text((runtime/'database_url').read_text().replace('127.0.0.1:17432', 'postgres:5432'))
            url.chmod(0o644)  # Disposable credential, private enclosing directory.
            appcommand=[DOCKER,'run','--rm','--network',project+'_app','--ip',app_ip,'-e','DATABASE_URL_FILE=/run/url','-e','DATABASE_SSL_CA_FILE=/run/ca.crt','-v',f'{url}:/run/url:ro','-v',f'{runtime / "ca.crt"}:/run/ca.crt:ro','-v',f'{ROOT.parent / "guten-datalake/app/database.py"}:/app/app/database.py:ro','--entrypoint','python',args.datalake_image,'-B','-c']
            probe="import asyncio; from sqlalchemy import text; from app.database import engine\nasync def check():\n async with engine.connect() as c:\n  assert (await c.execute(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()'))).scalar()\n  assert (await c.execute(text('SELECT count(*) FROM draft.pages'))).scalar() == 2\n await engine.dispose()\nasyncio.run(check())"
            run(appcommand+[probe])
            passed('Datalake application role connects with verified TLS')
            run(appcommand+["import asyncio; from sqlalchemy import text; from app.database import engine\nasync def check():\n async with engine.begin() as c: await c.execute(text('CREATE TABLE draft.forbidden(id int)'))\nasyncio.run(check())"], fails=True)
            passed('application role cannot create tables')
            run(compose+['run','--rm','-T','--entrypoint','psql','backup','-X','-v','ON_ERROR_STOP=1','-c',"INSERT INTO draft.pages(text) VALUES ('forbidden')"],fails=True)
            run(compose+['run','--rm','-T','-e','PGDATABASE=postgres','--entrypoint','psql','backup','-X','-c','SELECT 1'],fails=True)
            passed('backup role cannot modify content or connect to other databases')
            run([DOCKER,'run','--rm','-v',f'{temp}:/keys','--entrypoint','age-keygen','guten-postgres:17-tls','-o','/keys/identity'])
            recipient=run([DOCKER,'run','--rm','-v',f'{temp}:/keys','--entrypoint','age-keygen','guten-postgres:17-tls','-y','/keys/identity'])
            (runtime/'recipients.txt').write_text(recipient+'\n')
            backupcmd=compose+['run','--rm','-T','backup']
            run(backupcmd)
            archive=next((runtime/'backups').glob('guten_*'))
            assert not (archive/'INCOMPLETE').exists()
            assert not any(p.suffix=='.dump' for p in archive.iterdir())
            passed('encrypted backup completed without plaintext dump on disk')
            def restore(target, path=archive, identity=temp/'identity', fails=False):
                return run(compose+['run','--rm','-T','-e','PGUSER=postgres','-e','PGPASSFILE=/admin_pgpass','-v',f'{runtime / "admin_pgpass"}:/admin_pgpass:ro','-v',f'{path}:/archive:ro','-v',f'{identity}:/identity:ro','backup','restore','--archive','/archive','--identity','/identity','--target',target],fails=fails)
            restore('guten_restore_verified')
            query="SELECT json_agg(p ORDER BY id) FROM draft.pages p; SELECT json_agg(p ORDER BY id) FROM published.pages p; SELECT last_value FROM draft.pages_id_seq;"
            assert sql(query) == sql(query,'guten_restore_verified')
            passed('restore preserves draft/published Unicode content and sequence state')
            restore('guten_restore_verified',fails=True)
            restore('guten_datalake',fails=True)
            restore('vitaledge_restore',fails=True)
            passed('existing database, master, and unrelated targets refused')
            damaged=temp/'damaged'
            shutil.copytree(archive,damaged)
            with (damaged/'full.dump.age').open('ab') as f: f.write(b'tampered')
            restore('guten_restore_damaged',path=damaged,fails=True)
            meta=json.loads((damaged/'manifest.json').read_text())
            meta['sha256']=hashlib.sha256((damaged/'full.dump.age').read_bytes()).hexdigest()
            (damaged/'manifest.json').write_text(json.dumps(meta))
            restore('guten_restore_damaged',path=damaged,fails=True)
            assert sql("SELECT count(*) FROM pg_database WHERE datname='guten_restore_damaged'",'postgres')=='0'
            passed('checksum and authenticated decryption reject corruption before database creation')
            run(compose+['run','--rm','-T','-e','PGDATABASE=vitaledge','backup'],fails=True)
            run(compose+['run','--rm','-T','-e','PGSSLMODE=disable','backup'],fails=True)
            passed('backup refuses other projects and unverified TLS settings')
            # Bad recipient fails but never marks an archive complete.
            (runtime/'recipients.txt').write_text('not-an-age-recipient\n')
            run(backupcmd,fails=True)
            assert len(list((runtime/'backups').glob('*/INCOMPLETE')))==1
            passed('failed backup leaves INCOMPLETE marker')
            run(compose+['down'])
            run(compose+['up','-d','--wait','--wait-timeout','90','postgres'])
            assert sql('SELECT count(*) FROM draft.pages')=='2'
            passed('external volume survives container recreation')
        finally:
            log=subprocess.run(compose+['logs','--no-color','postgres'],capture_output=True,text=True)
            (artifact/'postgres.log').write_text(log.stdout)
            subprocess.run(compose+['down','--remove-orphans'],check=True)
            run([DOCKER,'volume','rm',volume])
            (artifact/'results.json').write_text(json.dumps({'passed':results},indent=2)+'\n')
    print('Results:',artifact)


if __name__ == '__main__':
    main()
