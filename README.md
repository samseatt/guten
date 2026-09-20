# Guten local operations

This repository holds project-wide documentation and the local command interface. The four application repositories remain siblings:

```text
guten/                    # parent directory
  guten/                  # this repository: run make here
  guten-datalake/
  guten-crust/
  guten-portal/
  guten-sites/
```

Run `make help` for available commands. Requirements are Python 3, Make, Node/npm, PostgreSQL client tools, and each service's existing dependencies. The command interface uses the Python standard library; acceptance tests additionally use the existing Datalake Python dependencies and the pinned Playwright development dependency.

## Everyday use

```bash
make status
make up
# Ctrl+C stops the processes started by make up.
# Or run individual services in separate terminals:
make run SERVICE=datalake
make run SERVICE=crust
make run SERVICE=portal
make run SERVICE=sites
```

The launcher uses the existing local port map: portal 3001, sites 3000, Crust 8000, Datalake 8005, native PostgreSQL 5432. It refuses occupied ports before starting services. It does not adopt, kill, or restart services launched elsewhere. Stop existing manually launched services in their original terminals before using it. Logs remain in the foreground; optional Datalake file logging is configured explicitly. An unexpectedly exiting child stops the other services started by that invocation.

`make status` reports TCP listeners, not application readiness. PostgreSQL is shared with other projects and is never started/stopped/reinitialized by this interface. The browser/API configuration remains in each service's existing environment setup.

Copy `local.mk.example` to ignored `local.mk` for machine-specific settings. Set `DATALAKE_PYTHON` to the Guten environment's Python, or invoke Make using an activated environment. `GUTEN_ROOT` can override the parent directory. The current Mac's local.mk selects its existing Guten Conda environment.

## Checks and builds

```bash
make check
make check SERVICE=crust
make build SERVICE=portal
```

Checks run TypeScript without emitting files and Python syntax validation without importing the application. They are not integration tests. Builds use Next.js production builds or TypeScript compilation; Python needs no compilation step beyond syntax validation here. Builds refuse selected services with occupied ports to avoid overwriting a running Next.js development build. Existing application type/configuration errors are reported; the operations tooling does not hide them. No dependency installation happens automatically.

## Database archives and recovery

```bash
make backup
make backup ARCHIVE_ROOT=/absolute/path/to/archive-parent
make restore ARCHIVE=/absolute/path/to/archive TARGET=guten_restore_20260916
```

These delegate to versioned backup/restore scripts in guten-datalake. Read that repository's `docs/psql/how-to-backup-psql.md` for contents, credentials, checksums, restore validation, and future RDS considerations. Backups include the entire Guten database, including draft, published, and workflow schemas. Restore requires a new guten_* database and refuses the live guten_datalake database or any existing target. Switch application connections only after deliberate validation. Keep media/repository archives as well as database archives, and copy completed archives off the Mac.

## Development and deployment sequence

1. Archive the live database before schema/content migrations.
2. Make a small change in the relevant service repositories.
3. Run checks and targeted tests; rehearse schema migrations on a restored database first.
4. Stop selected development services before production builds.
5. Review Git diffs in each affected repository; commit/push deliberately.
6. Verify the local content flow before any deployment.

Docker Compose packaging is now available alongside the native launcher. See [Docker setup and operations](docs/docker.md). GitHub login is available for Docker Portal; see [authentication](docs/authentication.md). The two Lightsail hosts and cloud database backups/monitoring are provisioned; Portal is deployed with GitHub authentication, and [guten.ink is live on AWS](docs/guten-site-cutover.md). [AWS is now the content master](docs/content-master.md); use production Portal for real edits. Other publication domains remain to be moved. The native Mac database is a development/reference snapshot.

See [storage and Git conventions](docs/storage-and-git.md) for media archives, commit boundaries, and the proposed S3 path design.

Database evolution: use `make migrate DATABASE=<rehearsal-db>` and `make test TEST_DATABASE=<guten_*_test_*>`. See [migration and ordering contract](../guten-datalake/docs/scoping-and-ordering.md).

See [per-site publishing](../guten-datalake/docs/publishing.md) for the editor workflow, API, migration, and initial publication seeding. Portal/View Draft reads draft; Guten Sites reads published content only.

## Repeatable acceptance tests

```bash
npm ci
make acceptance
```

This creates an empty disposable test database from committed schema/migrations, runs API and headless browser tests on isolated ports, then removes only that database and the processes it started. It does not require a content dump or stop development services. Logs, API results, browser HTML/JUnit reports, and failure traces remain under ignored `artifacts/`. See [testing and prerequisites](docs/testing.md), including browser setup for this Mac and Linux.

Environment examples are committed in each application repo. Datalake requires `DATABASE_URL`; both frontends share `NEXT_PUBLIC_API_BASE_URL`. Public frontend settings must contain no secrets. [Container packaging](docs/docker.md) also supports local rehearsals on alternate ports; see the cloud deployment runbooks below for the live hosts.

See [root pages and domain routing](docs/domain-routing.md) for the Portal home and recommended production addresses.

See [the agreed Lightsail deployment plan](docs/cloud-plan.md) for the two-host design, Caddy HTTPS and PostgreSQL 17 rehearsal.

See [HTTPS gateway setup and tests](docs/https-gateway.md) for explicit site domains and Caddy configuration.

See [PostgreSQL cloud packaging and encrypted recovery](docs/cloud-database.md) for the private TLS database host, daily backup templates and repeatable local integration test.

See [versioned releases and rollback](docs/releases.md) for committed-source image builds, digest-pinned application bundles and explicit deployment/schema guards.

See [bootstrap provisioning and cost controls](docs/provisioning-plan.md) for the resource allowlist, budget proposal and read-only AWS inventory command.

See [create the bootstrap infrastructure](docs/create-infrastructure.md) for the fixed CloudFormation stack and the prepared Admin CloudShell launch procedure.

See [initial application release preparation](docs/initial-app-release.md) for private GitHub packages and launch prerequisites, and [referenced media packaging](docs/media-packaging.md) for the separate image bundle.

See [app-host bootstrap](docs/cloud-app-bootstrap.md) for the production credential and verified media installation procedures.

See [Portal-first AWS launch](docs/portal-launch.md) for HTTPS, access checks, rollback evidence and the content-master boundary.

Live domain configuration: [five-domain batch](docs/batch2-cutover.md) adds BIGJ, C4A, Cancer, Caucer and DRX alongside Guten and Neubank. The cumulative manifest is `deploy/domains.batch2.json`.

Batch 3 adds Adama, See Eight and Glia; current cumulative routing is `deploy/domains.batch3.json`. See [remaining-domain progress](docs/remaining-domain-cutovers.md), including the open intermittent canonical-tag issue.

Batch 4 adds Kausar, Moxaic, Neuconomy, Neufacture and Neumm. Current cumulative configuration: `deploy/domains.batch4.json`; see [batch 4 verification](docs/batch4-cutover.md) for DNS-cache and user-acceptance status.

Batch 5 adds Neurocoin, NGOC8, Nudge, Nudger and Omix. Current cumulative configuration: `deploy/domains.batch5.json`; see [batch 5 verification](docs/batch5-cutover.md).

Batch 6 adds Physx, Xfin, Xgaia, Xjur and Xmos. Current cumulative routing: `deploy/domains.batch6.json`; see [batch 6 verification](docs/batch6-cutover.md).

Batch 7 adds Sysb and Xnome. Current live manifest: `deploy/domains.batch7.json`; the Cloudflare `batch8` manifest is staged, not live. See [final-domain progress](docs/final-nine-cutovers.md).

Batch 8 activates Neuverse, Tiers and Xmed after their Cloudflare DNS changes. Current live manifest: `deploy/domains.batch8.json` (30 publications plus Portal). See [Cloudflare cutover evidence](docs/cloudflare-publication-cutover.md).

The final ready-site release adds Adaprise, Ineural and Xtack (33 publications plus Portal). Active manifest: `deploy/domains.batch9-ready.json`. Convergent is staged pending recursive DNS convergence; see [final-four status](docs/final-four-cutover.md).
