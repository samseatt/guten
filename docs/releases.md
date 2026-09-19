# Versioned application releases and rollback

The release tools provide a manual, repeatable path suitable for later CI invocation. They do not provision AWS, upload code unless explicitly requested, change DNS, apply migrations or restore a database. A release covers the four apps plus OAuth2 Proxy, Nginx and Caddy. The separately managed PostgreSQL host is deliberately excluded.

## Release contract

A bundle records all five repository commit IDs, seven immutable image digests, exact database migration filenames/checksums, domain configuration and file checksums. App images must carry the `org.opencontainers.image.revision` label matching the recorded source commit. The initial platform is `linux/amd64`, matching the planned x86 Lightsail hosts and the Intel Mac.

Deployments use the fixed Compose project `guten-prod` and its network. Only Caddy publishes host ports 80/443. Credentials and media are host-mounted separately; the bundle includes neither. Caddy certificate data/config use pre-existing external volumes and survive release changes. Compose startup never builds images or performs migrations. This release path does not promise zero downtime on a single app host.

The migration contract is deliberately strict: the candidate image must see exactly its recorded migrations/checksums, using a read-only database transaction and its normal verified TLS connection. An older release is refused after incompatible schema advancement. A database restore is never an automatic response to an application deployment failure.

## 1. Build from committed sources

Commit reviewed code in all five repositories first. Both build and packaging commands refuse dirty repositories. Run the relevant acceptance/security checks for the change before choosing a release. The builder runs Docker builds serially from `git archive` exports, excluding ignored secrets, caches, dumps and PNG assets. Media is installed separately at `/srv/guten/assets`.

```bash
python3 scripts/build_release_images.py \
  --registry ghcr.io/samseatt \
  --output artifacts/build-record.json
```

This builds four local images without publishing them. Tags use full source commit IDs; the record includes revisions, tags and local image IDs. Public API paths are `/api`; Portal login is built enabled. Publication domains are runtime configuration, not per-site image builds. Base-image tags in existing app Dockerfiles still resolve at build time; the final deployment digest fixes the result. Save build records and acceptance evidence with the release.

When registry credentials/permissions have been deliberately configured and publishing is authorized, use `--push` with a new output path. It builds all four images and saves their local IDs before pushing any, then records each registry digest as its upload completes. A failed push may leave some images published; it does not deploy them. Retry the saved record without rebuilding:

```bash
python3 scripts/publish_release_images.py artifacts/build-record.json
```

The retry verifies all four local image IDs, architecture and source labels before uploading. Missing or changed images stop the upload. Re-pushing the same images is idempotent; successful digests are saved after each push. Old records without local image IDs cannot be retried automatically. Keep the record on the build machine until publication completes; package only a record with all four registry digests. This is still a manual release path, not an unattended GitHub Actions deployment.

## 2. Pin the complete image set and package

Create an `images.json` object mapping exactly `datalake`, `crust`, `portal`, `sites`, `auth`, `web` and `caddy` to image references in the form `registry/repository@sha256:<64 lowercase hex characters>`. Use the app digests from the published build record. Resolve reviewed versions of the three gateway/auth images to digests as well; auth/Caddy versions are recorded in the committed Compose/generator, while Nginx must also be pinned for the release. No `latest` or tag-only references are accepted.

Use your reviewed production domain manifest:

```bash
python3 scripts/package_release.py \
  --id guten-20260918-01 \
  --images /ABSOLUTE/PATH/images.json \
  --domains /ABSOLUTE/PATH/domains.json \
  --output artifacts/releases/guten-20260918-01
python3 scripts/deploy_release.py plan artifacts/releases/guten-20260918-01
```

The example release ID is illustrative. Use a new ID each time; output directories are never overwritten. Packaging renders the existing Compose and gateway configuration, removes build directives/local port bindings, sets fixed production paths and validates the resulting Compose file. It requires Docker Compose tooling but does not pull, build or start containers. The plan command checks bundle consistency/checksums and prints the release contract without accessing AWS, Docker or the database.

Retain the bundle unchanged at `/opt/guten/releases/<release-id>` on the app host. Generated config mounts use that immutable directory, not a movable `current` symlink. Protect releases as root-owned, non-writable by application users. Checksums detect accidental corruption; they are not signatures. Transfer bundles through a trusted channel and trust their source: Docker configuration and the bundled runner are executable deployment inputs.

## 3. Host prerequisites

Provisioning will install and verify these before the first release:

- Docker with Compose supporting `up --wait`, Python 3, registry pull credentials, trusted DNS/time and HTTPS reachability.
- External volumes `guten-caddy-data` and `guten-caddy-config` (create once; never repurpose existing unrelated volumes).
- `/srv/guten/assets`, readable by the frontend container users.
- `/etc/guten/secrets/database_url`, `database_ca.crt`, `oauth2-proxy.cfg`, `github_client_secret`, `oauth_cookie_secret`.
- `/var/lib/guten/deployments`, reserved for deployment status and a process lock.
- Database private networking/TLS, reviewed database contents/roles/migrations, real GitHub OAuth callback configuration and domain DNS.

The Datalake secret must be readable by UID/GID 10001; OAuth secrets by UID/GID 65532. Use appropriate root-owned group-readable 0640 files inside a private host directory, and public CA/config permissions only where needed. Never make private keys/passwords generally readable merely to solve a mount problem. See [database operations](cloud-database.md) and [authentication](authentication.md).

Initial certificate issuance still needs DNS and open ports 80/443. Validate public HTTPS with ACME staging before production issuance as described in the cloud plan. The release smoke checks require trusted production HTTPS; they will fail on internal/self-signed test certificates. Do not disable verification to bypass this.

## 4. Deploy explicitly

On the app host:

```bash
sudo python3 /opt/guten/releases/guten-20260918-01/deploy_release.py \
  apply /opt/guten/releases/guten-20260918-01
```

Under a deployment lock, the runner verifies the bundle, pulls pinned images, checks app-image architecture/source labels and checks database schema compatibility. Only then does it record an attempt and run `compose up -d --no-build --pull never --wait`. It checks the Portal sign-in page and each configured publication's health endpoint over verified HTTPS. Only a successful run advances `last_successful` and `previous` in the state file.

A preflight failure leaves running services and deployment state unchanged (pulled images or the one-off database-check container may have been created). A later failure can leave partially replaced services and records a failed attempt. Inspect logs and explicitly roll back; the runner does not silently attempt additional changes. Logs/state remain on the host; external failure notification remains deployment work. Health probes establish service/TLS reachability, not complete editorial/OAuth workflow acceptance; run those separately before public cutover.

## 5. Inspect and roll back

```bash
sudo python3 /opt/guten/releases/guten-20260918-01/deploy_release.py status
sudo python3 /opt/guten/releases/guten-20260918-01/deploy_release.py rollback
```

After a healthy deployment, rollback selects the previous successful release. After a failed/interrupted attempt, it selects the last successful release. It rechecks image provenance and the database migration contract and redeploys that intact bundle. A first-ever failed deployment has no previous release; fix/retry it after inspecting logs. Retain prior bundles and registry digests so recovery remains possible.

Rollback does not revert database content, media, credentials, OAuth configuration or certificates. Coordinate changes to those separately. No `compose down`, volume deletion, database downgrade or migration runs in this tool. If a migration contract prevents rollback, plan recovery deliberately rather than bypassing the check.

## Verification and remaining deployment work

```bash
python3 -B -m unittest discover -s tests -p test_releases.py -v
```

The tests render real Compose bundles and validate ports, TLS settings, immutable images/configuration, corruption detection, release-state transitions, failure/rollback selection, image revision checks and database-probe behavior. Host mutations, network health probes and registry calls are mocked in controller tests. These are not evidence of a successful AWS deployment. Existing end-to-end gateway/database tests cover the underlying services separately.

Next: prepare and review exact AWS resources and host bootstrap/firewall steps; provision; configure registry access and production secrets; rehearse a real deployment/rollback on test domains. Wire GitHub Actions to invoke the same reviewed build/package commands after the manual path has been demonstrated. Do not add unattended production deployment before that rehearsal.

Recorded local result: nine release tests passed on September 17, 2026 (local time); report retained at `artifacts/release_20260918T015035Z/tests.log`. The build-context test uses real temporary Git repositories/archives and a mocked Docker builder to verify ignored secrets are excluded. Registry publishing and cloud deployment were not performed.
