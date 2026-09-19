# Portal-first AWS launch

Cloudflare remains the authoritative DNS provider; Namecheap remains the registrar. Sam added a DNS-only A record for `portal.guten.ink` pointing to `52.54.75.169`. The main `guten.ink` record still points at Cloudflare Pages, and no publication domain has been cut over.

## Completed checks

- Production credentials validated and installed; the server uses a separate read-only GitHub Packages token. Archive `.cloud-app` privately, including the cookie key. Token expiry: December 18, 2026, 03:40:16 UTC.
- All seven pinned images pulled on Lightsail; app source labels/architecture and the read-only PostgreSQL TLS migration check passed.
- Six internal services started without host ports. `scripts/test_cloud_app_private.cjs`, run inside the Docker network, checked anonymous/spoofed access denial, OAuth redirect and secure cookie settings, 34-site read access, and the shared Portal image checksum. Sites rejects all unconfigured hosts in Portal-only mode.
- The private probe uses Node's HTTP client to preserve an explicit Host header. Node fetch overrode that header in the first probe; the host allowlist correctly returned 404. The probe also explicitly expects Sites image requests to return 404 until publication domains exist.
- `scripts/prepare_acme_staging.py` generated a separate single-domain rehearsal with maintenance responses, no application upstream/network, and isolated staging certificate storage. Real Caddy adaptation verified its sole issuer is Let's Encrypt staging. Two guard tests passed.
- External inspection confirmed a staging certificate for exactly `portal.guten.ink` and HTTP 503 maintenance response. The staging container was then stopped. Its volumes were retained separately; they are never mounted into production.
- Production certificate volumes `guten-caddy-data` and `guten-caddy-config` were created. Release `guten-portal-20260919-01` applied successfully with trusted HTTPS smoke verification.

Evidence is retained under ignored `artifacts/`: `cloud-app-preflight-20260919.log`, `cloud-private-checks-20260919.log`, `acme-staging-proof-20260919.json`, `cloud-portal-deployment-20260919.log`, and `cloud-portal-public-checks-20260919.json`. Certificate inspection disables verification only in the explicitly isolated staging probe; production verification uses the normal trusted certificate store and hostname checks.

## Repeatable operations

Run these commands on the app host using sudo:

```bash
python3 /opt/guten/releases/guten-portal-20260919-01/deploy_release.py status
python3 /opt/guten/releases/guten-portal-20260919-01/deploy_release.py apply /opt/guten/releases/guten-portal-20260919-01
```

The release controller preserves the certificate volumes and media. Never use a routine volume-prune command on this host. A future release must be packaged as a new immutable directory; do not edit an installed bundle. Read [releases and rollback](releases.md) before rolling back. The first release alone has no previous successful release to select.

To repeat the private check, run `scripts/test_cloud_app_private.cjs` through stdin to `docker compose ... exec -T crust node - portal.guten.ink <default-image-sha256>`. Take the checksum from the archived media manifest. The script never logs cookies or modifies content.

## Next acceptance and content boundary

Real GitHub authorization still needs Sam's manual test at `https://portal.guten.ink/dashboard`, including viewing a draft page and checking its image. Portal's View Published links intentionally remain unavailable while its publication map is empty.

Use view-only access during this acceptance phase. The native Mac database remains the content master until a deliberate switch is agreed; avoid editing both databases independently. Public site DNS changes and any final content refresh are separate cutover work. Preserve the existing Cloudflare Pages site until the AWS public site is verified.
