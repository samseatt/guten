#!/usr/bin/env python3
"""Generate private PostgreSQL host configuration; creates no cloud resources."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--database-ip', required=True)
    p.add_argument('--app-ip', required=True)
    p.add_argument('--backup-subnet', default='172.29.77.0/24')
    p.add_argument('--port', type=int, default=5432)
    p.add_argument('--test', action='store_true', help='Allow loopback IPs for disposable local tests.')
    a = p.parse_args()
    ips = [ipaddress.IPv4Address(v) for v in (a.database_ip, a.app_ip)]
    if any(not ip.is_private or ip.is_unspecified or ip.is_multicast or ip.is_link_local or (ip.is_loopback and not a.test) for ip in ips):
        p.error('Use private IPv4 addresses; loopback requires --test.')
    subnet = ipaddress.IPv4Network(a.backup_subnet)
    if not subnet.is_private or subnet.prefixlen != 24 or any(ip in subnet for ip in ips):
        p.error('Use an unused private /24 Docker subnet that does not overlap either host address.')
    if not 1024 <= a.port <= 65535:
        p.error('Port must be between 1024 and 65535.')
    os.umask(0o077)
    a.output.mkdir(parents=True, exist_ok=False)
    root = a.output.resolve()
    offline = root / 'offline'
    runtime = root / 'runtime'
    offline.mkdir()
    runtime.mkdir()
    (runtime / 'backups').mkdir()
    def openssl(*args):
        subprocess.run(['openssl', *map(str, args)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    openssl('req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-sha256', '-days', '3650', '-subj', '/CN=Guten Database CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', offline/'ca.key', '-out', runtime/'ca.crt')
    openssl('req', '-new', '-newkey', 'rsa:3072', '-nodes', '-sha256', '-subj', '/CN=Guten PostgreSQL', '-keyout', runtime/'server.key', '-out', offline/'server.csr')
    extension = offline/'server.ext'
    extension.write_text(f'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:{a.database_ip},DNS:postgres\n')
    openssl('x509', '-req', '-in', offline/'server.csr', '-CA', runtime/'ca.crt', '-CAkey', offline/'ca.key', '-CAcreateserial', '-days', '365', '-sha256', '-extfile', extension, '-out', runtime/'server.crt')
    # Certificates/configs need to be readable by the postgres container user;
    # enclosing directories and all credential files remain private.
    for name in ('ca.crt', 'server.crt'):
        (runtime/name).chmod(0o644)
    password = secrets.token_urlsafe(36)
    (runtime/'postgres_password').write_text(password + '\n')
    (runtime/'admin_pgpass').write_text(f'postgres:5432:*:postgres:{password}\n')
    app_password = secrets.token_urlsafe(36)
    backup_password = secrets.token_urlsafe(36)
    (runtime/'pgpass').write_text(f'postgres:5432:guten_datalake:guten_backup:{backup_password}\n')
    (runtime/'database_url').write_text(f'postgresql+asyncpg://guten_app:{app_password}@{a.database_ip}:{a.port}/guten_datalake\n')
    # Run explicitly only after restoring the database and reviewing schema names.
    # Passwords contain only URL-safe characters, never quotes or backslashes.
    (runtime/'bootstrap-roles.sql').write_text(f'''\\set ON_ERROR_STOP on
\\connect guten_datalake
BEGIN;
CREATE ROLE guten_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{app_password}';
CREATE ROLE guten_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{backup_password}';
REVOKE ALL ON DATABASE guten_datalake FROM PUBLIC;
GRANT CONNECT ON DATABASE guten_datalake TO guten_app, guten_backup;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA draft, published, workflow TO guten_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA draft, published, workflow TO guten_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA draft, published, workflow TO guten_app;
GRANT USAGE ON SCHEMA draft, published, workflow, public TO guten_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA draft, published, workflow, public TO guten_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA draft, published, workflow, public TO guten_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA draft, published, workflow GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO guten_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA draft, published, workflow GRANT USAGE, SELECT ON SEQUENCES TO guten_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA draft, published, workflow, public GRANT SELECT ON TABLES TO guten_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA draft, published, workflow, public GRANT SELECT ON SEQUENCES TO guten_backup;
COMMIT;
''')
    (runtime/'recipients.txt').write_text('# Replace with your age public recipient; keep the private identity offline.\n')
    (runtime/'postgresql.conf').write_text("""listen_addresses = '*'
password_encryption = 'scram-sha-256'
ssl = on
ssl_min_protocol_version = 'TLSv1.2'
ssl_cert_file = '/etc/guten/server.crt'
ssl_key_file = '/run/guten-tls/server.key'
hba_file = '/etc/guten/pg_hba.conf'
shared_buffers = '256MB'
max_connections = 60
log_connections = on
log_disconnections = on
log_statement = 'none'
""")
    (runtime/'pg_hba.conf').write_text(f'''# Unix sockets are container-local administration only.
local all postgres peer
local all all reject
hostnossl all all 0.0.0.0/0 reject
hostnossl all all ::/0 reject
hostssl guten_datalake guten_app {a.app_ip}/32 scram-sha-256
# Backup/admin clients run in this host's dedicated Docker network.
hostssl guten_datalake guten_backup {subnet} scram-sha-256
hostssl all postgres {subnet} scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject
''')
    for name in ('postgresql.conf', 'pg_hba.conf'):
        (runtime/name).chmod(0o644)
    # JSON is valid YAML and avoids another generator dependency.
    mounts = [f'./{name}:/etc/guten/{name}:ro' for name in ('postgresql.conf','pg_hba.conf','server.crt','ca.crt')]
    compose = {
        'name': 'guten-cloud-db',
        'services': {
            'postgres': {
                'image': 'guten-postgres:17-tls', 'restart': 'unless-stopped',
                'environment': {'POSTGRES_USER':'postgres','POSTGRES_DB':'postgres','POSTGRES_PASSWORD_FILE':'/run/secrets/postgres_password','POSTGRES_INITDB_ARGS':'--encoding=UTF8 --locale=C.UTF-8 --auth-host=scram-sha-256'},
                'secrets':['postgres_password','server_key'],
                'volumes':['pgdata:/var/lib/postgresql/data', *mounts],
                'tmpfs':['/run/guten-tls'],
                'ports':[f'{a.database_ip}:{a.port}:5432'],
                'healthcheck':{'test':['CMD-SHELL','gosu postgres pg_isready -U postgres -d postgres'],'interval':'10s','timeout':'5s','retries':6},
                'stop_grace_period':'60s',
                'logging':{'driver':'json-file','options':{'max-size':'10m','max-file':'3'}},
            },
            'backup': {
                'image':'guten-postgres:17-tls','profiles':['ops'],
                'entrypoint':['guten-archive'],
                'command':['backup','--root','/backups','--recipient-file','/run/secrets/recipients'],
                'environment':{'PGHOST':'postgres','PGPORT':'5432','PGUSER':'guten_backup','PGDATABASE':'guten_datalake','PGPASSFILE':'/run/secrets/pgpass','PGSSLMODE':'verify-full','PGSSLROOTCERT':'/etc/guten/ca.crt','PGCONNECT_TIMEOUT':'10','AWS_DEFAULT_REGION':'us-east-1'},
                'secrets':['pgpass','recipients'],
                'volumes':['./backups:/backups', './ca.crt:/etc/guten/ca.crt:ro'],
                'tmpfs':['/tmp'], 'read_only':True, 'cap_drop':['ALL'],
                'security_opt':['no-new-privileges:true'],
            },
        },
        'volumes':{'pgdata':{'external':True,'name':'${GUTEN_PG_VOLUME:?Set a dedicated PostgreSQL 17 volume name}'}},
        'networks':{'default':{'ipam':{'config':[{'subnet':str(subnet)}]}}},
        'secrets':{name:{'file':'./'+filename} for name,filename in [('postgres_password','postgres_password'),('server_key','server.key'),('pgpass','pgpass'),('recipients','recipients.txt')]},
    }
    (runtime/'compose.yaml').write_text(json.dumps(compose, indent=2)+'\n')
    print(f'Generated {root}. Keep offline/ off the server; review runtime/ before deployment.')


if __name__ == '__main__':
    main()
