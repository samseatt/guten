# PostgreSQL cloud host: packaging and recovery

This package was locally rehearsed and is now deployed to the Guten Lightsail database host. Content restoration, TLS/role checks, encrypted S3 recovery and daily scheduling are complete; external backup alerts, retention and application cutover are pending. See [cloud-database-bootstrap.md](cloud-database-bootstrap.md) for the live checkpoint. It uses PostgreSQL 17 in a dedicated external Docker volume, private IPv4 binding, TLS with server identity verification, SCRAM passwords, separate application/backup roles, encrypted logical archives and explicit restore commands. The native Mac PostgreSQL installation, VitalEdge databases and existing PostgreSQL 14 Docker stack are unchanged.

## Files and boundaries

- `scripts/configure_database.py`: generates fresh host configuration and certificates. Refuses an existing output directory.
- `deploy/database/Dockerfile`: PostgreSQL 17 base pinned by digest, plus Debian-packaged age, Python and AWS CLI. Record/pin the resulting image digest in the eventual release manifest; package repositories can change between builds.
- `deploy/database/archive.py`: encrypted logical backup and guarded new-database restore.
- `deploy/compose.database-tls.yaml`: Datalake application-host override.
- `deploy/database/systemd/`: Linux daily backup service/timer templates.
- `scripts/test_cloud_database.py`: disposable integration tests with synthetic content.

These templates need the two actual private IPs and an unused Docker subnet. PostgreSQL binds only the database host's private IP. Its HBA permits `guten_app` to access Guten from the application host IP, and the backup/admin roles from the dedicated database Docker subnet. Plaintext TCP and other clients are rejected. Do not attach unrelated workloads to that Docker network.

At deployment also install Docker-aware host forwarding/firewall restrictions allowing port 5432 only from the application host, and verify from an unauthorized private-network client. Lightsail's public firewall alone is insufficient for private traffic. Public 5432 must remain closed. These host firewall rules are now installed on both Guten Lightsail hosts and independently verified; they are managed separately from Compose. See [cloud-hosts.md](cloud-hosts.md) for scope, persistence and test evidence.

## Build and generate (no AWS access required)

From the operations repository:

```bash
docker build -t guten-postgres:17-tls deploy/database
python3 scripts/configure_database.py --output .cloud-database \
  --database-ip 10.0.0.10 --app-ip 10.0.0.11
```

Replace the example addresses with the real private addresses when known. The output is ignored by Git and contains private credentials. `offline/ca.key` is the database CA private key: retain securely off the servers. `runtime/` contains the server key, public CA/certificate, database passwords, app URL, bootstrap SQL, configuration, Compose file and backup directory. Transfer only the necessary files to each host over a trusted encrypted channel. Keep the database directory root-owned mode 0700; secret files mode 0600. Public certificates/config files generated mode 0644 permit container users to read them. Compose secrets are mounted files, not an encrypted secret store.

Transfer a trusted archive of the contents of `runtime/` (never `offline/`) through `sudo sh deploy/database/install-runtime.sh` on the database host. It refuses an existing target, extracts into `/etc/guten/database/`, preserves required file modes, and assigns ownership to root. Do not preserve Mac file ownership: libpq will ignore a password file owned by a different UID. The app host needs only `database_url` and `ca.crt`, not administrative/backup credentials or the server private key. On that host set the URL file owner/group to `root:10001` and mode 0640 so the Datalake container (UID/GID 10001) can read its mounted secret; retain a private enclosing directory. Its CA certificate can remain mode 0644. Native local configuration still works without TLS; the cloud Compose override explicitly requires `DATABASE_SSL_CA_FILE`. With that setting, Datalake verifies both trust and hostname/IP and rejects conflicting SSL URL options.

The server certificate has a one-year lifetime, covers the configured private IP and the internal Docker hostname `postgres`, and requires deliberate renewal with the offline CA. Before expiry: generate a replacement server key/certificate with the same identities, deploy both, recreate the PostgreSQL container against the same external volume so new bind-mounted files are picked up, and test verified connections. Changing the private IP requires a replacement certificate and application configuration. The backup service reports failure after an otherwise successful backup if certificate expiry is within 30 days. This is not automatic certificate renewal.

The new cluster explicitly uses UTF-8 / `C.UTF-8`. It does not promise identical locale sorting to the Mac's `en_CA.UTF-8`; content ordering uses explicit sort order. Review any locale-sensitive queries during cutover. Never point PostgreSQL 17 at a PostgreSQL 14 data volume.

## Initial host start and database import

On the database host, after installing the reviewed image:

```bash
docker volume create guten-cloud-pg17
# /etc/guten/database.env (mode 0600):
# GUTEN_PG_VOLUME=guten-cloud-pg17
# GUTEN_BACKUP_S3_PREFIX=s3://YOUR-BUCKET/guten/database

docker compose --env-file /etc/guten/database.env \
  -f /etc/guten/database/compose.yaml up -d --wait postgres
```

The external volume must already exist; routine Compose teardown cannot remove it. The initial cluster contains only the administration database. No migration, content import, role creation or database replacement runs automatically.

Take and verify a fresh native Guten archive before cutover. Import its `full.dump` into a **new** database on this fresh cluster, using `pg_restore --single-transaction --exit-on-error --no-owner --no-privileges --no-tablespaces`. Verify tables, row counts, sequence state, migrations and application acceptance before deliberately naming it `guten_datalake`. Initial import/cutover will be performed as a separate reviewed deployment step; the existing native archive is not in the new age-encrypted archive format.

After `draft`, `published`, `workflow` and migration metadata have been restored, initialize roles once:

```bash
docker compose --env-file /etc/guten/database.env \
  -f /etc/guten/database/compose.yaml exec -T --user postgres postgres \
  psql -X -d postgres < /etc/guten/database/bootstrap-roles.sql
```

This transaction refuses existing role names. It revokes public database access, grants the app CRUD in the Guten schemas, and gives `guten_backup` read access only. The app cannot create schemas/tables or administer the cluster. Backups do not capture roles/passwords; retain protected deployment configuration separately. Future migrations must run as `postgres` for the supplied default privileges to apply; review grants if a different migration owner is introduced. Other projects will need their own database, roles, connection rules and backup procedures.

On the app host, combine the application and gateway configuration with `deploy/compose.database-tls.yaml`, set `GUTEN_DATABASE_URL_FILE` and `GUTEN_DATABASE_CA_FILE` to their installed paths, and use the database's private IP in the URL. Do not combine this with the local rehearsal database network override.

## Encryption and manual backup

Generate an age recovery identity on a trusted local machine. The tool is also present in the image; use a private local directory mounted at `/keys`:

```bash
docker run --rm -v /ABSOLUTE/PRIVATE/RECOVERY-DIRECTORY:/keys \
  --entrypoint age-keygen guten-postgres:17-tls -o /keys/guten-backup-identity
```

Save the private identity securely in at least two independent locations. Put only the printed public `age1...` recipient into the database host's `recipients.txt`. The server does not need the recovery identity to make backups. Missing/invalid recipients fail the backup and retain an `INCOMPLETE` marker.

```bash
docker compose --env-file /etc/guten/database.env \
  -f /etc/guten/database/compose.yaml run --rm -T backup
```

Each unique archive contains `full.dump.age` and `manifest.json` with a ciphertext checksum and tool version. One `pg_dump` snapshot includes every Guten schema, including draft/published/workflow. No plaintext archive is persisted during backup. Both dump and encryption exit codes must succeed before the completion marker is removed. Dumping another database or using anything other than `PGSSLMODE=verify-full` is refused. This is logical recovery, not point-in-time recovery; daily backups imply potentially losing a day's edits.

Keep media backups as well. The archive contains database content and image references, not PNG files.

## Off-host upload and scheduling

Create the S3 backup bucket/prefix, public-access blocking, versioning and lifecycle deliberately during provisioning. Configure a dedicated upload identity scoped to that prefix (no read/delete rights unless specifically needed). The included `aws s3 cp` flow may need multipart-upload permissions in addition to PutObject for large archives; verify the final policy with the deployed AWS CLI. Do not copy the personal Admin/GutenAudit session to a server. Lightsail server credential delivery/rotation is still a deployment decision.

Install the reviewed `compose.upload.example.yaml` as `/etc/guten/database/compose.upload.yaml` and provide the dedicated credential file it references. First test upload manually:

```bash
docker compose --env-file /etc/guten/database.env \
  -f /etc/guten/database/compose.yaml \
  -f /etc/guten/database/compose.upload.yaml run --rm -T backup \
  backup --root /backups --recipient-file /run/secrets/recipients \
  --s3-prefix s3://YOUR-BUCKET/guten/database
```

Ciphertext uploads first, manifest last; both must succeed for an `UPLOADED` receipt locally. Remote recovery requires both files and successful checksum/decryption. Upload failure fails the job but preserves the completed local archive. The ciphertext is already age-encrypted; upload additionally requests S3 SSE-S3 encryption. Real S3 upload/download and independent restore have now passed; see [cloud-backup-activation.md](cloud-backup-activation.md).

Install the two unit files into `/etc/systemd/system/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl start guten-backup.service
sudo systemctl enable --now guten-backup.timer
systemctl list-timers guten-backup.timer
journalctl -u guten-backup.service
```

The job runs daily around 03:00 UTC with a short randomized delay, catches up missed runs, and uses a lock to avoid concurrent scheduled backups. The service has now been tested on the Linux database host and the timer enabled; its detailed status is in [cloud-backup-activation.md](cloud-backup-activation.md). **Before live cutover**, wire failed/missed backups and low disk space into an external notification, and verify an uploaded archive can be downloaded and restored. Service exit status/journal alone is not an off-host alert.

No automatic archive deletion is enabled. Initially keep all backups; configure and test S3 lifecycle and conservative local retention before unattended production operation. Local deletion must require successful off-host upload and an adequate verified recovery history. Account for failed/incomplete backups in disk monitoring.

## Restore rehearsal

Download both archive files to a trusted recovery host. Use a **new** `guten_restore_*` database. Run with administrative credentials mounted separately; the routine backup account cannot create databases:

```bash
docker compose --env-file /etc/guten/database.env \
  -f /etc/guten/database/compose.yaml run --rm -T \
  -e PGUSER=postgres -e PGPASSFILE=/admin_pgpass \
  -v /etc/guten/database/admin_pgpass:/admin_pgpass:ro \
  -v /ABSOLUTE/ARCHIVE:/archive:ro \
  -v /ABSOLUTE/RECOVERY-IDENTITY:/identity:ro \
  backup restore --archive /archive --identity /identity \
  --target guten_restore_rehearsal
```

Prefer a separate recovery machine for off-server identity protection; if temporarily mounting the identity on the database host, remove that copy afterward. Checksum and authenticated decryption finish before a database is created. Decryption uses temporary plaintext storage (`/tmp` is tmpfs in the service); size recovery memory/storage for the uncompressed custom dump. Restoring existing targets, the master name, or other projects is refused. Restore is transactional; a failure after database creation leaves the new target for inspection and deliberately does not drop it. Recreate app grants and validate content before any separate cutover. Never blindly restore untrusted SQL archives as an administrator.

## Local integration test

```bash
python3 scripts/test_cloud_database.py
```

Requires the built `guten-postgres:17-tls` and existing `guten-datalake:local` images, Docker, Python 3 and OpenSSL. It generates temporary secrets/certificates, chooses isolated Docker subnets, creates a unique external PG17 volume, exercises TLS rejection/success, actual Datalake asyncpg connectivity, role boundaries, encrypted backup/restore, tampering/restore guards and volume persistence, then removes its containers, networks, volume and temporary secrets. Existing networks with overlapping subnets cause a safe startup failure; rerun after checking the network inventory. Reports and PostgreSQL logs remain in ignored `artifacts/database_*`.

Reference behavior: [PostgreSQL TLS verification](https://www.postgresql.org/docs/17/libpq-ssl.html), [HBA authentication](https://www.postgresql.org/docs/17/auth-pg-hba-conf.html), [age encryption](https://github.com/FiloSottile/age).

## Recorded local result

September 17, 2026 (local time): all 14 TLS/roles/archive/restore/persistence checks passed. Report: `artifacts/database_20260918T011050Z_7148a48496/results.json`. All four Datalake startup-configuration tests also passed. The test database, volume, networks and temporary keys were removed; the existing application/rehearsal stack stayed healthy.
