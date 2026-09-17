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

Docker Compose packaging is now available alongside the native launcher. See [Docker setup and operations](docs/docker.md). AWS provisioning, authentication and deployment automation remain later work; native master backups are unchanged.

See [storage and Git conventions](docs/storage-and-git.md) for media archives, commit boundaries, and the proposed S3 path design.

Database evolution: use `make migrate DATABASE=<rehearsal-db>` and `make test TEST_DATABASE=<guten_*_test_*>`. See [migration and ordering contract](../guten-datalake/docs/scoping-and-ordering.md).

See [per-site publishing](../guten-datalake/docs/publishing.md) for the editor workflow, API, migration, and initial publication seeding. Portal/View Draft reads draft; Guten Sites reads published content only.

## Repeatable acceptance tests

```bash
npm ci
make acceptance
```

This creates an empty disposable test database from committed schema/migrations, runs API and headless browser tests on isolated ports, then removes only that database and the processes it started. It does not require a content dump or stop development services. Logs, API results, browser HTML/JUnit reports, and failure traces remain under ignored `artifacts/`. See [testing and prerequisites](docs/testing.md), including browser setup for this Mac and Linux.

Environment examples are committed in each application repo. Datalake requires `DATABASE_URL`; both frontends share `NEXT_PUBLIC_API_BASE_URL`. Public frontend settings must contain no secrets. Authentication and cloud deployment remain subsequent work; [container packaging](docs/docker.md) runs locally on alternate ports.
