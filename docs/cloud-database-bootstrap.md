# PostgreSQL cloud bootstrap checkpoint

Completed September 18, 2026 local time (September 19 UTC). PostgreSQL 17.11 runs on `guten-db-01`, private IPv4 `172.26.4.118`, in external volume `guten-cloud-pg17`. It binds TCP 5432 only to that private address. The Docker firewall accepts this port only from the application host `172.26.5.8`. The Mac PostgreSQL installation and its databases remain unchanged. No application traffic or DNS has been cut over.

## Source and validation

The previous archived rehearsal had 34 publishing-log entries; the native database has 40. Therefore a fresh read-only backup was taken instead of reusing that older archive:

`guten-datalake/db_dump/guten_datalake_20260919T001303Z_QCNJsZ/`

All archive checksums passed. `full.dump` was transferred over pinned-host-key SSH, rechecked on the destination, and restored transactionally into a newly created `guten_restore_cloud_20260919` database. Restore used `--no-owner --no-privileges --no-tablespaces --single-transaction --exit-on-error`.

Native and cloud fingerprints match for all 19 tables (row counts and SHA-256 of canonically ordered JSON rows), 17 sequence states, 125 column definitions/defaults/nullability flags, and 32 index definitions. Fingerprints normalize session timezone to UTC, use read-only transactions, and require edits to remain paused while comparing (each query uses its own connection). Five CHECK constraints differ only in equivalent array/text-cast rendering between PostgreSQL 14 and 17; their names and allowed values were reviewed. Other constraint definitions match. This comparison does not claim a general automated proof of arbitrary cross-version SQL equivalence.

Only after comparison was the staging database renamed to `guten_datalake`. No existing cloud master database was overwritten. The supplied bootstrap SQL created the application and backup roles and revoked public database access. A second disposable restore using the saved import script matched the first cloud fingerprint and was removed afterward. Attempts to reuse a target, restore directly to the master name, or overwrite existing runtime configuration were rejected.

## Runtime and secrets

The image was built on the database host from the repository's pinned PostgreSQL 17 base and reviewed Dockerfile. Installed Compose services reference the exact local image ID:

`sha256:3ae4a34996586cd9bb9f6f1e4411ce0fb08b196d1ecb0390cc346ecd6a530891`

This is a local image ID, not a published registry digest. A registry-backed release is still pending. The host can restart using its local image; retain build provenance and do not prune this image.

Database configuration is `/etc/guten/database/`, root-owned and private. It includes server certificates/passwords, `compose.yaml` and backup-role configuration. `/etc/guten/database.env` selects the external volume. Only the application URL and public CA certificate were copied to `/etc/guten/secrets/` on the app host. The URL is root:10001 mode 0640 for the future Datalake container. The private CA key remains on the Mac under ignored `.cloud-database/offline/` and was never transferred to either server.

A live backup-client check caught Mac UID ownership preserved by tar. libpq ignored that password file. Runtime ownership is now root:root, and `deploy/database/install-runtime.sh` explicitly avoids preserving source ownership. It preserves public-certificate readability and protects secret file modes.

Keep the local `.cloud-database/` directory in protected independent storage: it includes the CA key and recovery/configuration credentials. Keep it out of Git and public archives. Also archive the new native dump above. The existing earlier archive remains intact.

## Verified access

The saved `scripts/test_cloud_database_access.py` ran from the actual application host using a disposable pinned PostgreSQL client container:

- Application login succeeds with CA and server-IP verification over TLS 1.3; 34 sites are readable.
- Application role has intended page CRUD rights and no schema/database creation, superuser, role-administration or database-administration rights.
- Plaintext connections are rejected by HBA.
- An incorrect server identity is rejected by certificate verification.
- Administrator login originating from the app host is rejected by HBA.

A separate backup-service test authenticated `guten_backup` using verified TLS 1.3, read all 34 published sites, and confirmed SELECT permission without INSERT permission. No backup upload or schedule is active yet.

Scripts retained in the repository:

- `scripts/fingerprint_database.py`: read-only source/restore comparison artifact generator; `--psql-command` must be the last option and can wrap `docker exec … psql`.
- `scripts/test_cloud_database_access.py`: cross-host TLS, identity rejection and role checks; run as root on the configured app host.
- `deploy/database/install-runtime.sh`: first-time runtime installation from a trusted runtime-only tar stream; refuses replacement.
- `deploy/database/import-native.sh`: checksum-verified native dump import into a new `guten_restore_*` database; refuses master names and existing targets. A failed restore leaves the new target for inspection rather than deleting it.

Build/start/restore, fingerprint, role and acceptance logs are retained under ignored `.cloud-provision/`. The database host retains the imported dump and comparison reports under private `/var/lib/guten/import-20260919/` for this deployment checkpoint. The native dump is plaintext content protected by directory permissions and SSH transport; it is not the encrypted cloud backup format.

## Operations and next checkpoint

On the database host:

```bash
sudo docker compose --env-file /etc/guten/database.env \
  -f /etc/guten/database/compose.yaml ps
```

The cloud content is a verified copy, not yet the editorial master. Continue treating the local database as the master until deliberate application cutover; any subsequent local edits require a reviewed refresh, not blindly rerunning an import over the cloud database.

Next: configure an offline age recovery identity, a prefix-scoped S3 upload identity, encrypted manual backup and independent restore verification, then enable and monitor the daily backup schedule. S3 policy inspection, retention and external failure alerts remain pending. Do not treat a running cloud database as a completed backup strategy. App release packaging, media transfer, production OAuth and DNS/HTTPS cutover follow after recovery is verified.
