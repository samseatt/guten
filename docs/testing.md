# Repeatable tests

Run commands from the coordination repository (`guten/`, alongside the four service repos).

## Prerequisites

- Install each application's existing dependencies and select its Python using `DATALAKE_PYTHON` in ignored `local.mk`.
- PostgreSQL must already be running. The test role needs permission to create databases. Standard PostgreSQL `PG*` settings apply; use the local development server. Tests never use the application's `DATABASE_URL` to choose their database.
- Run `npm ci` in this repository to install the pinned Playwright test dependency.
- On this Intel Mac/macOS 13, the current Playwright bundled Chromium is unsupported. The runner defaults to the installed Google Chrome (`PLAYWRIGHT_CHANNEL=chrome`), launching a fresh temporary profile with no access to your normal browser session. Verified with Chrome 152.0.7977.84. Browser updates can affect test compatibility.
- On supported Linux CI, run `npx playwright install --with-deps chromium` once. The runner defaults to bundled Chromium there. `PLAYWRIGHT_CHANNEL` can explicitly choose an installed channel.

## Full acceptance run

```bash
make acceptance
```

The runner creates a unique `guten_acceptance_test_<uuid>` database, applies the committed baseline and all numbered migrations, then runs:

1. Python configuration/guard tests and real PostgreSQL + FastAPI + Crust integration tests. These cover scoped names, ordering, references/notes validation and CRUD, publication isolation/idempotence/concurrency/rollback, unpublish, and readiness failure/recovery.
2. Three browser scenarios against all four services: editorial add/edit/cancel/delete and failed saves; ordering through reload/preview/publication; publish confirmation, draft/public isolation, stale review rejection and unpublish.

All fixtures are synthetic. The runner chooses temporary loopback ports, explicitly supplies the disposable database and API addresses, and never reuses a running application server. Frontend source/config files are copied to temporary directories; installed node_modules are linked, while local environment files, media and `.next` builds are excluded. Missing content images in these fixtures are expected; media delivery is outside this suite.

Normal completion, errors, and Ctrl+C stop owned process groups and drop only the newly created database. Existing databases are never overwritten. A forced process kill or machine crash can leave a uniquely named test database behind; inspect before manually removing it. Database cleanup failure is reported as a failed command, not hidden.

Reports remain under `artifacts/<run-id>/`:

- `api-results.txt`, `api-results.json`, `api-services.log`
- individual service logs
- `browser-report/index.html`, `browser-results.xml`
- failure screenshots and traces under `browser-results/`
- `run.json` records success and database removal

These files are ignored by Git. The test definitions and dependency lockfile are committed. Archive a report folder when retaining evidence for a release. There is no automatic retention/deletion policy yet.

## Focused API run

```bash
make test-db TARGET=guten_manual_test_1
make test TEST_DATABASE=guten_manual_test_1
```

The first command refuses existing databases and creates an empty current schema. The second starts isolated API services and retains results under `guten-datalake/test-results/`. It does not remove this explicitly requested database; fixtures are cleaned up. Do not run multiple test suites simultaneously against the same database because the readiness/rollback tests temporarily change test-only database objects.

## Checks and production builds

```bash
make check
make build
```

Checks validate Python syntax and application TypeScript. Builds validate production compilation; stop the ordinary application services first to avoid overwriting their build output. These complement acceptance tests, which currently exercise development-mode Next.js servers. There is no claim of full security, performance, migration-from-every-historical-version, or production-container coverage. Add deployment/authentication tests with those features.
