#!/usr/bin/python3
"""Encrypted PostgreSQL logical archives. Restore creates a NEW database only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    backup = commands.add_parser('backup')
    backup.add_argument('--root', type=Path, required=True)
    backup.add_argument('--recipient-file', type=Path, required=True)
    backup.add_argument('--s3-prefix', help='Optional s3://bucket/prefix; upload failure fails the job.')
    restore = commands.add_parser('restore')
    restore.add_argument('--archive', type=Path, required=True)
    restore.add_argument('--identity', type=Path, required=True)
    restore.add_argument('--target', required=True)
    args = parser.parse_args()
    if os.environ.get('PGSSLMODE') != 'verify-full' or not os.environ.get('PGSSLROOTCERT'):
        parser.error('PGSSLMODE=verify-full and PGSSLROOTCERT are required.')
    if args.command == 'backup':
        database = os.environ.get('PGDATABASE', '')
        if database != 'guten_datalake':
            parser.error('Backup requires PGDATABASE=guten_datalake; other projects are excluded.')
        if args.s3_prefix and not re.fullmatch(r's3://[a-z0-9][a-z0-9.-]+/[A-Za-z0-9_/-]+', args.s3_prefix):
            parser.error('Use an explicit s3://bucket/prefix with no wildcards.')
        args.root.mkdir(parents=True, exist_ok=True)
        archive = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('guten_%Y%m%dT%H%M%SZ_'), dir=args.root))
        incomplete = archive / 'INCOMPLETE'
        incomplete.touch()
        encrypted = archive / 'full.dump.age'
        # No plaintext archive is written to disk. Check BOTH processes, including
        # pg_dump failures that would otherwise produce a valid encrypted partial dump.
        dump = subprocess.Popen(['pg_dump', '--format=custom', '--no-owner', '--no-privileges', database], stdout=subprocess.PIPE)
        try:
            encryption = subprocess.run(['age', '-R', str(args.recipient_file), '-o', str(encrypted)], stdin=dump.stdout)
        finally:
            dump.stdout.close()
            dump_code = dump.wait()
        if encryption.returncode or dump_code:
            raise RuntimeError('Backup failed; INCOMPLETE archive retained for inspection.')
        metadata = {
            'format': 1, 'database': database,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'pg_dump_version': subprocess.check_output(['pg_dump', '--version'], text=True).strip(),
            'sha256': digest(encrypted),
        }
        (archive / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
        incomplete.unlink()
        if args.s3_prefix:
            destination = args.s3_prefix.rstrip('/') + '/' + archive.name + '/'
            # Manifest goes last: a remote directory with only ciphertext is incomplete.
            for name in ('full.dump.age', 'manifest.json'):
                run(['aws', 's3', 'cp', str(archive / name), destination + name, '--only-show-errors', '--sse', 'AES256'])
            (archive / 'UPLOADED').write_text(destination + '\n')
        print(archive)
    else:
        if not re.fullmatch(r'guten_restore_[a-z0-9_]+', args.target) or len(args.target) > 63:
            parser.error('Restore target must be a NEW guten_restore_* database (maximum 63 characters).')
        if (args.archive / 'INCOMPLETE').exists():
            raise RuntimeError('Refusing incomplete archive.')
        metadata = json.loads((args.archive / 'manifest.json').read_text())
        encrypted = args.archive / 'full.dump.age'
        if metadata.get('format') != 1 or metadata.get('database') != 'guten_datalake' or digest(encrypted) != metadata.get('sha256'):
            raise RuntimeError('Archive manifest/checksum validation failed.')
        # Authenticate/decrypt completely before creating a database. Mount TMPDIR
        # as tmpfs on recovery hosts: a plaintext dump exists here during restoration.
        with tempfile.TemporaryDirectory(prefix='guten-restore-') as directory:
            dump = Path(directory) / 'full.dump'
            run(['age', '--decrypt', '-i', str(args.identity), '-o', str(dump), str(encrypted)])
            run(['pg_restore', '--list', str(dump)], stdout=subprocess.DEVNULL)
            run(['createdb', '--template=template0', args.target])
            run(['pg_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-privileges', '--no-tablespaces', '--dbname', args.target, str(dump)])
        print(f'Restored {args.target}. Validate before any deliberate application cutover; ownership/grants are separate.')


if __name__ == '__main__':
    main()
