# Initial application release preparation

Application images use private GitHub Container Registry packages under `ghcr.io/samseatt`. The four repositories are `guten-datalake`, `guten-crust`, `guten-portal` and `guten-sites`. The first build is local on the Intel Mac, targeting Linux amd64; production hosts pull immutable digests and never build from GitHub source. GitHub Actions can later invoke the same release tools.

## Credentials and package visibility

Local publishing uses a short-lived classic GitHub personal access token with `write:packages` and `read:packages`, without `repo` or `delete:packages`. Sign in using `docker login ghcr.io --username samseatt` and enter the token at the password prompt. Docker Desktop stores it in its credential store; do not put it in Git, environment examples, command arguments, release records or chat. New GHCR packages are private by default; verify every package's visibility after publishing.

The cloud host must receive a separate token with only `read:packages`, from an account permitted to read all four private packages. Do not transfer the publishing token to Lightsail. Record the pull token's expiry and rotate it before a deployment needs it; token expiration does not stop already-running containers but prevents new pulls. Retain digests needed for rollback.

Reference: [GitHub Container Registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Inputs prepared locally

- `deploy/domains.initial.json`: 34 publication domains and `portal.guten.ink`. Glia is `glia.cash`, as confirmed by Sam. No `www` aliases are assumed. This is a deployment input, not a DNS change.
- [Referenced media bundle](media-packaging.md): 301 selected files, original sources preserved. One existing missing favicon is explicitly acknowledged.
- `artifacts/build-20260919-published.json`: records full app source commits, local image IDs, tags and all four registry digests. The associated build log and `publish-20260919-retry*.log` capture builds and pushes. `artifacts/registry-verification-20260919.json` independently records private visibility and matching remote commit-tag digests. These artifacts are ignored by Git and should accompany the archived release evidence.

Building from `git archive` exposed an empty Portal `public` directory that was absent from Git. Portal's Dockerfile now creates the directory before its production build. Media remains a separate runtime mount.

## Remaining before public launch

1. Configure the separate read-only pull credential on the app host and verify pulls of all four private digests.
2. Install the checksummed media bundle; retain its manifest and a recoverable previous version.
3. Create a separate GitHub OAuth App for production, homepage `https://portal.guten.ink`, callback `https://portal.guten.ink/oauth2/callback`. Install its secret and a new cookie key privately; the allowed editor remains `samseatt`.
4. Review domain ownership/current DNS and stage a limited initial cutover. Pin auth, web and Caddy images; package the release with the reviewed domain list. Validate routing and authentication before broad DNS changes and certificate issuance.
5. Perform the first controlled deployment, real GitHub login, content/image checks and rollback rehearsal. Keep local content unchanged during the cutover; publishing images alone does not switch the editorial master to AWS.

No additional AWS resources are needed for this image/media preparation. No application is deployed by the build or media scripts. Database backups and monitoring remain separate services on the database host.

## Completed verification, September 18, 2026

All four Linux amd64 images were built from committed Git archives and published. GitHub's package API confirmed all four are private and their remote commit tags resolve to the recorded digests. Portal's fixed runtime directory and entry point were checked in a network-isolated container. The test suites passed: six media tests, nine release tests, three domain tests and three registry retry tests. These checks do not replace the forthcoming cloud/OAuth acceptance test.

GitHub returned HTTP 500 when finalizing initial uploads. Retrying the same verified images succeeded. The initial build record was reconstructed from the completed local image IDs and verified source labels because the old builder saved its record only after all pushes. The builder now saves before publication; the new `publish_release_images.py` retries that record and checkpoints each successful digest. No rebuild or credential change was needed for the successful retry.

Archive the published build record, registry verification report, media inventory and tar alongside the existing database/credential archives. Registry tokens are not included in those artifacts. Application deployment, host media installation, production OAuth setup and DNS cutover have not yet occurred.
