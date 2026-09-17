# Docker Compose packaging

This is a local production-build rehearsal, not a public cloud deployment. It runs beside the native services and never connects to native PostgreSQL. The master Guten content and VitalEdge databases are unchanged.

## Structure

- Each application repository owns its Dockerfile and .dockerignore. Python uses 3.11, Node uses 22; npm ci and the committed Python requirements preserve application dependency versions.
- Frontends use Next.js standalone production output. Crust compiles TypeScript and removes development dependencies. All four application processes run as non-root users.
- `deploy/compose.apps.yaml` owns the four applications, OAuth2 Proxy and an unprivileged Nginx proxy. Only the proxy publishes ports, bound explicitly to 127.0.0.1.
- `deploy/compose.database.yaml` owns PostgreSQL with an external named volume. No database port is published locally.
- `deploy/compose.local.yaml` joins Datalake to the separate local database network and provides an explicit, one-time rehearsal initializer. Do not use this overlay on separate cloud hosts.

The database image retains PostgreSQL major 14 for compatibility with the current Mac. Plan its supported-major upgrade before cloud deployment; do not change a database image's major version against an existing volume. Base images track explicit major/distribution tags; release CI should record/pin resolved digests and refresh them deliberately.

## First setup

Run from this repository. Docker Desktop/Engine and Compose v2.24.4+ with `up --wait` and `!override` are required; install the existing test dependencies with `npm ci` to run browser tests.

```bash
make docker-setup
make auth-setup        # configure GitHub credentials; see docs/authentication.md
make docker-build
make docker-db-up
make docker-init-test
make docker-up
make docker-test
make docker-test-lifecycle
```

Setup writes random credentials under ignored `.docker-local/`, and refuses to replace existing files. This directory is mode 0700; secret files are readable inside their explicitly selected non-root containers. Do not change the directory to world-readable or commit it. Compose file secrets are bind mounts, not an encrypted secrets vault. Datalake supports `DATABASE_URL_FILE`; the URL/password never enters Docker build arguments or frontend bundles.

The initializer creates only a NEW `guten_compose_test_local` database, applies the baseline/migrations, and grants a separate `guten_app` role the necessary data privileges. The application role has no superuser, database creation, role creation, or schema creation rights. The admin credential is mounted only in PostgreSQL and the explicitly invoked initializer. Initialization refuses existing databases; app startup never migrates or overwrites content. On partial initialization failure, inspect the error and database rather than repeatedly resetting it.

- Portal: http://localhost:13001/dashboard
- Sites: http://localhost:13000/<site-name>

This database begins empty. Browser tests create and clean up synthetic sites. Existing site content is still served by the native services at ports 3000/3001. No master dump is restored automatically.

## Daily operations

```bash
make docker-up         # start apps/proxy, wait for health; DB must already be running
make docker-status     # show both projects
make docker-logs       # recent app/proxy logs
make docker-stop       # stop apps/proxy only
make docker-down       # remove apps/proxy containers, leave DB and its volume alone
make docker-db-stop    # explicit, separate database stop
make docker-db-up      # restart DB using its existing persistent volume
make docker-build      # rebuild production images after source changes
make docker-up         # recreate changed app containers
```

`make docker-up` validates the auth configuration and recreates the gateway services to load changed routing or credentials; application containers are recreated only when needed. App commands do not stop the database. No provided command removes a database volume. The named volume `guten-local-pgdata` is external even to the database project; Compose down (including -v) does not remove it. Docker volume removal/pruning is a separate, potentially destructive administrator action. Persistence is not a backup.

The local helper checks the volume's Guten rehearsal label before adopting it. Existing unrelated Docker containers/volumes are not managed. Native `make up`, `make backup`, and `make acceptance` remain available and unchanged in purpose.

## Routing, media and configuration

Browser API calls use same-origin `/api`, forwarded to Crust, which addresses Datalake through Compose DNS. Container hostnames never appear in browser URLs. The public Sites listener permits only GET/HEAD under `/api/guten/published/` and rejects other API paths/methods. The Portal listener protects pages and editorial APIs with GitHub authentication. See [authentication setup](authentication.md).

The existing `guten-sites/public/assets` directory is mounted read-only into both frontends, so `/assets/...` can work in containerized Portal previews as well as Sites. Images are not copied into images, moved, regenerated, or committed. Override `GUTEN_ASSETS_DIR` with an existing absolute directory if needed. Central S3 media delivery remains later work.

`GUTEN_PUBLIC_SITES_URL` is a frontend BUILD argument used by Portal's View Published link; rebuild Portal when it changes. `/api` itself stays portable. See `deploy/environment.example`. A future deployment can use `compose.apps.yaml` alone with a secret pointing to the database host's private address. That is a packaging foundation, not yet a ready-to-expose Lightsail configuration: private firewall rules/TLS, HTTPS domains, image registry/CI and backup scheduling still need implementation.

## Verification and backups

`make docker-test` creates a temporary isolated auth-test stack on ports 13010–13012, verifies the rehearsal database target, and tests real OAuth proxy behavior using fake GitHub accounts plus the stored browser workflows. It tears down only that temporary stack and retains reports/logs in ignored `artifacts/auth_<run-id>/`. See [authentication coverage](authentication.md). `make docker-test-lifecycle` separately verifies non-root processes, hidden backend ports, shared read-only media, and database persistence by replacing the normal rehearsal containers while retaining the volume. Its fixture setup and media checks use internal container requests so they do not need a human login. It briefly interrupts the Docker rehearsal stack only and retains a JSON report.

To make a rehearsal dump without installing host PostgreSQL tools:

```bash
mkdir -p .docker-local/backups
docker compose -f deploy/compose.database.yaml exec -T postgres pg_dump -U postgres -Fc guten_compose_test_local > .docker-local/backups/rehearsal.dump
```

Use a new filename for each dump; shell redirection overwrites an existing file. Copy completed backups off the machine and rehearse restore into a NEW test database. Native master backups still use `make backup`; its fixed master target has deliberately not been redirected to this rehearsal cluster. Production container backup/restore automation will be completed with cloud database provisioning, credentials and retention choices.

Application dependency security updates are recorded in [security maintenance](security-maintenance.md). Local-only port bindings are intentional and should not be loosened as a shortcut.

Implementation references: [Docker startup/health ordering](https://docs.docker.com/compose/how-tos/startup-order/), [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/), [Next.js standalone packaging](https://docs.docker.com/guides/nextjs/).
