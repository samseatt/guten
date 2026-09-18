# Hostname routing and HTTPS gateway

Guten's cloud gateway uses Caddy in front of the existing Nginx/OAuth2 Proxy stack. Caddy owns ports 80/443, certificate acquisition/renewal and HTTP redirects. Nginx continues enforcing editorial authentication, CSRF Origin checks and published-only reads. App/backend ports are not published. This implements gateway packaging; AWS hosts, DNS ownership and production credentials still require provisioning.

## Explicit domains

Use `deploy/domains.example.json` as a starting point. List each site's internal slug, its canonical hostname and optional aliases. `portal` is the separate authenticated workspace hostname. The generator rejects duplicate names, duplicate canonical site mappings, invalid slugs and directive injection. It does not infer mappings from database URL metadata or prove domain ownership. Verify ownership before adding a domain.

```bash
python3 -B scripts/configure_domains.py \
  --manifest /absolute/path/to/approved-domains.json \
  --output /absolute/path/to/new-gateway-release
```

Output contains a Caddyfile, Nginx config, domain manifest and Compose overlay. Generation refuses to overwrite an existing directory. Use a new release directory for each change, review the diff, and retain the previous release for rollback. Production output opens public 80/443; generating files alone does not start services or contact a certificate authority.

The gateway overlay is applied after `deploy/compose.apps.yaml` and the future cloud-host settings. It removes the local Nginx port bindings. Do not combine `compose.local.yaml` with production: that file explicitly connects to the local rehearsal database and supplies HTTP OAuth settings. Runtime frontend variables carry the allowlist; generated JSON is deployment configuration, not a secret. There is no need to rebuild images to change the host map.

For a mapped public host, `/` and `/section` select the published landing page; `/section/page` serves content. Menu links omit the internal site slug. Existing Markdown links beginning with the current site's `/<slug>/` are made domain-relative; external links are preserved. Native development still uses `/<site>/<section>/<page>` when no map is set. Shared `/assets/`, Next.js resources and health endpoints retain their purpose. Canonical metadata uses the configured HTTPS origin and page path, excluding query strings.

Public API access is limited to GET/HEAD for `/api/guten/published/sites/<mapped-site>/landing` and `/page`; another site's slug and editorial routes are rejected. Portal's View Published link goes through an authenticated Portal redirect that selects the configured canonical public origin. A site without a configured domain returns a clear 404 instead of guessing a URL. Local Portal retains its configured path-based Sites URL fallback.

## Production prerequisites

- Point the verified A records and intended aliases at the application host's static IP. Do not publish incorrect AAAA records. Keep existing DNS providers if desired.
- Configure a separate production GitHub OAuth App with callback `https://<portal-host>/oauth2/callback`, an allowlist of approved GitHub users, fresh cookie secret and credential files outside Git/images. Keep local OAuth setup separate.
- Use the production image build with `NEXT_PUBLIC_AUTH_ENABLED=true`. API calls use `/api`; backend URLs and credentials are server-only.
- Preserve Caddy's named `caddy_data` and `caddy_config` volumes across releases; protect/back up their contents, which include private keys. Never prune/remove them as routine deployment cleanup. Caddy must remain able to renew certificates. Test ACME against staging before first public issuance.
- Only Caddy reaches the internal Nginx listeners. The generated Nginx config explicitly forwards HTTPS to OAuth. Do not expose these listeners or put an untrusted proxy in front without revisiting forwarded-header trust.
- Unknown hostnames are not configured for TLS/content; alias redirects use fixed approved destinations. No arbitrary on-demand certificate issuance is enabled.

## Repeatable local tests

These use the existing empty/synthetic Docker rehearsal database, not the native master. Start that database first. Build separate test image tags, leaving normal running containers unchanged:

```bash
docker build -t guten-sites:gateway-test ../guten-sites
docker build --build-arg NEXT_PUBLIC_AUTH_ENABLED=true -t guten-portal:gateway-test ../guten-portal
python3 -B -m unittest discover -s tests -p test_domain_config.py -v
python3 -B scripts/test_gateway.py
```

The runner generates `.test` domains with an internal Caddy CA and binds only loopback ports 14443/18080 plus 13022 for fake GitHub. Chrome resolves the test names to loopback; no DNS or system trust-store changes occur. Browser certificate verification is relaxed only for this internal-CA test. Public ACME issuance remains a deployment-stage verification.

The suite checks root/deep-link rendering, canonical URLs, navigation, publication scoping, aliases, HTTP-to-HTTPS redirects, unknown hosts, spoofed headers, HTTPS OAuth callbacks, secure host-only cookies, CSRF rejection, Portal published links, logout, and authentication outage behavior. It checks the rehearsal connection before fixture creation, creates unique synthetic sites and removes them afterward. The test Compose project has a unique name and its certificate volumes are disposable. Browser traces and service logs remain under ignored `artifacts/gateway_*`.

References: https://caddyserver.com/docs/automatic-https and https://nextjs.org/docs/15/pages/api-reference/file-conventions/middleware.

## Verification — September 17, 2026

- Production builds of Sites and Portal passed, including type checks (existing image-optimization lint warnings remain).
- Three domain-configuration guard tests passed.
- Generated production Caddy configuration parsed, and Nginx configuration passed `nginx -t`, both in network-disabled containers.
- HTTPS/browser/authentication checks and the authentication-outage check passed: `artifacts/gateway_20260917T181106_b40e5db4bd/`.
- Native regression rerun passed all 17 API/configuration tests and all 3 browser workflows: `artifacts/20260917T181310_771504802c/`.

An earlier overlapping native run timed out during cold compilation; running it separately passed without increasing timeouts. Gateway test development caught a browser Fetch assertion error and a nonstandard-port HTTP redirect issue; both were corrected before the successful run. Test stacks and fixtures were removed. No public DNS, certificates, AWS resources, master content or normal running Docker images were changed by these tests.
