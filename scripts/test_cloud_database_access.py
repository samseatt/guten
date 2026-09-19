#!/usr/bin/env python3
"""Run on the app host as root: authenticate with TLS, check permissions and rejection paths."""
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlparse,unquote

IMAGE='postgres:17-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0'


def main():
    url=urlparse(Path('/etc/guten/secrets/database_url').read_text().strip())
    ca='/etc/guten/secrets/database_ca.crt'
    with tempfile.TemporaryDirectory(prefix='guten-db-probe-',dir='/run') as directory:
        pgpass=Path(directory)/'pgpass'
        password=unquote(url.password).replace('\\','\\\\').replace(':','\\:')
        pgpass.write_text(f'*:*:*:{url.username}:{password}\n')
        pgpass.chmod(0o600)
        def probe(options,query):
            env={'PGHOST':url.hostname,'PGHOSTADDR':url.hostname,'PGPORT':str(url.port),'PGUSER':url.username,'PGDATABASE':url.path[1:],'PGPASSFILE':'/run/pgpass','PGSSLMODE':'verify-full','PGSSLROOTCERT':'/run/ca.crt','PGCONNECT_TIMEOUT':'5',**options}
            args=['docker','run','--rm','--network','host','--entrypoint','psql','--mount',f'type=bind,src={pgpass},dst=/run/pgpass,readonly','--mount',f'type=bind,src={ca},dst=/run/ca.crt,readonly']
            for k,v in env.items():args+=['-e',k+'='+v]
            return subprocess.run(args+[IMAGE,'-X','-A','-t','-v','ON_ERROR_STOP=1','-c',query],capture_output=True,text=True)
        result=probe({},"SELECT current_user, ssl, version FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
        assert result.returncode==0,result.stderr
        assert result.stdout.startswith('guten_app|t|TLSv1.'),result.stdout
        print('Authenticated app-host connection:',result.stdout.strip())
        result=probe({},"SELECT count(*) FROM draft.sites; SELECT (has_table_privilege(current_user,'draft.pages','SELECT') AND has_table_privilege(current_user,'draft.pages','INSERT') AND has_table_privilege(current_user,'draft.pages','UPDATE') AND has_table_privilege(current_user,'draft.pages','DELETE')),has_schema_privilege(current_user,'draft','CREATE'),has_database_privilege(current_user,current_database(),'CREATE'); SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user")
        assert result.returncode==0,result.stderr
        lines=result.stdout.strip().splitlines()
        assert lines[1:]==['t|f|f','f|f|f'],lines
        print('Site count and restricted role privileges:',json.dumps(lines))
        for label,options,expected in [
            ('plaintext',{'PGSSLMODE':'disable'},'pg_hba.conf rejects'),
            ('wrong server identity',{'PGHOST':'wrong.invalid'},'does not match'),
            ('administrator from app host',{'PGUSER':'postgres','PGDATABASE':'postgres'},'pg_hba.conf rejects'),
        ]:
            result=probe(options,'SELECT 1')
            assert result.returncode!=0 and expected in result.stderr,(label,result.stderr)
            print(label+': rejected as expected')

if __name__=='__main__':main()
