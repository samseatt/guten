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

Run `make help` for available commands. Requirements are Python 3, Make, Node/npm, PostgreSQL client tools, and each service's existing dependencies. No new runtime package is required by the command interface.

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

The launcher uses the existing local port map: portal 3001, sites 3000, Crust 8000, Datalake 8005, native PostgreSQL 5432. It refuses occupied ports before starting services. It does not adopt, kill, or restart services launched elsewhere. Stop existing manually launched services in their original terminals before using it. Logs remain in the foreground and existing application log files. An unexpectedly exiting child stops the other services started by that invocation.

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

Docker/container commands and AWS deployment are future additions after application build and configuration issues are resolved. This first version keeps the existing native services usable. It does not include placeholder deployments, change database topology, install Docker, push Git, or provision AWS. The command interface can later dispatch container builds/Compose and deployment tooling without replacing database archive scripts.

See [storage and Git conventions](docs/storage-and-git.md) for media archives, commit boundaries, and the proposed S3 path design.
