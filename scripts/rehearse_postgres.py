"""Compare a trusted Guten archive on PostgreSQL 14/17, then run acceptance on 17.

Requires Docker and the Datalake Python environment plus acceptance prerequisites.
Only newly created, uniquely named containers and their anonymous volumes are removed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(args):
    return subprocess.check_output(args, text=True).strip()


def fingerprint(port, password):
    result = {"tables": {}, "sequences": {}}
    with psycopg2.connect(host="127.0.0.1", port=port, user="postgres",
                          password=password, dbname="guten_restore_test_archive") as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2")
            tables = cur.fetchall()
            for schema, table in tables:
                cur.execute(sql.SQL('SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY to_jsonb(t)::text COLLATE "C"').format(sql.Identifier(schema), sql.Identifier(table)))
                digest, count = hashlib.sha256(), 0
                for (row,) in cur:
                    digest.update(row.encode() + b'\n')
                    count += 1
                result["tables"][schema + "." + table] = {"rows": count, "sha256": digest.hexdigest()}
            cur.execute("SELECT schemaname, sequencename FROM pg_sequences WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2")
            for schema, sequence in cur.fetchall():
                cur.execute(sql.SQL('SELECT last_value, is_called FROM {}.{}').format(sql.Identifier(schema), sql.Identifier(sequence)))
                result["sequences"][schema + "." + sequence] = list(cur.fetchone())
            cur.execute("SELECT n.nspname,c.relname,x.conname,pg_get_constraintdef(x.oid) FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3")
            result["constraints"] = [list(row) for row in cur.fetchall()]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    if (archive / "INCOMPLETE").exists():
        raise RuntimeError("Archive is marked incomplete")
    checksums = (archive / "SHA256SUMS").read_text().splitlines()
    expected = [line.split()[0] for line in checksums if line.endswith("  full.dump")]
    if len(expected) != 1 or hashlib.sha256((archive / "full.dump").read_bytes()).hexdigest() != expected[0]:
        raise RuntimeError("Missing or invalid full.dump checksum")
    token = uuid.uuid4().hex[:12]
    artifacts = ROOT / "artifacts" / ("postgres17_" + time.strftime("%Y%m%dT%H%M%S") + "_" + token)
    artifacts.mkdir(parents=True)
    report = {"passed": False, "archive": str(archive), "archive_sha256": expected[0], "servers": {}, "cleanup": {}}
    created = []
    password = secrets.token_hex(32)
    try:
        with tempfile.TemporaryDirectory(prefix="guten-pg-rehearsal-") as temporary:
            secret = Path(temporary) / "password"
            secret.write_text(password)
            secret.chmod(0o600)
            for major in (14, 17):
                name = f"guten-pg{major}-rehearsal-{token}"
                image = f"postgres:{major}-bookworm"
                # The image tag is for a NEW cluster only, never an existing PG14 volume.
                ident = output(["docker", "create", "--name", name, "--label", "guten.rehearsal="+token,
                    "-p", "127.0.0.1::5432", "-e", "POSTGRES_PASSWORD_FILE=/run/secrets/password",
                    "--mount", f"type=bind,src={secret},dst=/run/secrets/password,readonly",
                    "--mount", f"type=bind,src={archive},dst=/archive,readonly", image])
                created.append(ident)
                run(["docker", "start", ident], stdout=subprocess.DEVNULL)
                deadline = time.monotonic() + 90
                port = int(output(["docker", "port", ident, "5432/tcp"]).rsplit(":", 1)[1])
                while True:
                    try:
                        conn = psycopg2.connect(host="127.0.0.1", port=port, user="postgres", password=password, dbname="postgres", connect_timeout=2)
                        conn.close()
                        break
                    except psycopg2.OperationalError:
                        if time.monotonic() > deadline:
                            raise RuntimeError(f"PostgreSQL {major} startup timed out")
                        time.sleep(.5)
                run(["docker", "exec", ident, "createdb", "-U", "postgres", "-T", "template0", "guten_restore_test_archive"])
                with (artifacts / f"restore-{major}.log").open("w") as log:
                    run(["docker", "exec", ident, "pg_restore", "-U", "postgres", "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges", "--no-tablespaces", "-d", "guten_restore_test_archive", "/archive/full.dump"], stdout=log, stderr=log)
                restored = fingerprint(port, password)
                (artifacts / f"fingerprint-{major}.json").write_text(json.dumps(restored, indent=2)+"\n")
                report["servers"][str(major)] = {"image_id": output(["docker", "inspect", "--format", "{{.Image}}", ident]), "port": port}
            left = json.loads((artifacts / "fingerprint-14.json").read_text())
            right = json.loads((artifacts / "fingerprint-17.json").read_text())
            if left != right:
                raise RuntimeError("Restored tables, sequences or constraints differ; see fingerprint reports")
            report["restore_matches"] = True
            env = dict(os.environ, PGHOST="127.0.0.1", PGPORT=str(report["servers"]["17"]["port"]), PGUSER="postgres", PGPASSWORD=password, PGDATABASE="postgres", DATABASE_URL_FILE="", PGSSLMODE="disable")
            # acceptance.py creates/drops a DIFFERENT synthetic test database.
            with (artifacts / "acceptance.log").open("w") as log:
                run([sys.executable, "-B", str(ROOT / "scripts/acceptance.py")], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            report["passed"] = True
    finally:
        for ident in reversed(created):
            # IDs originate only from successful docker create calls in this invocation.
            result = subprocess.run(["docker", "rm", "-f", "-v", ident], capture_output=True, text=True)
            report["cleanup"][ident] = result.returncode == 0
        if not all(report["cleanup"].values()):
            report["passed"] = False
        (artifacts / "results.json").write_text(json.dumps(report, indent=2)+"\n")
        print(f"Rehearsal reports: {artifacts}", flush=True)
    if not report["passed"]:
        raise RuntimeError("Rehearsal failed; inspect retained reports")


if __name__ == "__main__":
    main()
