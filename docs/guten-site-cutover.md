# Guten public-site cutover

This release adds only the published `guten` site at `guten.ink`, plus `www.guten.ink` redirecting to the canonical hostname. Portal stays at `portal.guten.ink`. Other publication domains and all email DNS records are outside this change. Namecheap remains the registrar and Cloudflare remains the DNS provider.

## Pre-cutover evidence

`scripts/prepare_public_preview.py` prepares two temporary containers using the pinned Sites/Nginx images and existing cloud backends. Only app-host loopback port 18082 is published. Unique service aliases avoid replacing the live services. An SSH tunnel makes that preview available to the Mac; no public DNS or certificate changes are required.

The read-only `scripts/test_public_site.mjs` test uses `GUTEN_PREVIEW_BASE=http://127.0.0.1:18082` to route browser requests through that tunnel with the intended hostname. It tests actual published data without creating fixtures. On this Intel Mac set `PLAYWRIGHT_CHANNEL=chrome`; the Playwright-bundled browser is not installed.

The AWS preview passed: root redirected to `/guten_ink/guten_ink`, both images loaded, the canonical URL was correct, menu navigation and hard reload worked, and editorial/other-site APIs were rejected, including spoofed publication headers. There were no uncaught browser errors. The screenshot was visually checked. Evidence: `artifacts/guten-preview-browser-20260919-chrome/`.

## DNS change and rollback values

Sam confirmed these original Cloudflare records (both TTL Auto):

| Name | Original type/target | Original proxy | New type/target | New proxy |
| --- | --- | --- | --- | --- |
| guten.ink (@) | CNAME → guten.pages.dev | Proxied | A → 52.54.75.169 | DNS only |
| www | CNAME → guten.pages.dev | Proxied | CNAME → guten.ink | DNS only |

Keep TTL Auto. Preserve MX records pointing at registrar-servers.com and all unrelated TXT/email records. Do not delete the Cloudflare Pages project. If Cloudflare marks the record managed/locked by Pages, inspect that condition before removing any domain association; record-only rollback may then require reattaching the Pages custom domain too.

After DNS is changed, verify both hostnames resolve to the Lightsail app IP and have no stale explicit AAAA destination. Apply the prepared immutable release; Caddy obtains trusted certificates for the new names. Some resolvers may retain the old Pages destination during the prior TTL. Check trusted HTTPS, www/HTTP redirects, published content and Portal before declaring the cutover complete.

If the public-site cutover fails, restore these two original CNAME/proxy values to return visitors to Pages, then deliberately roll the app release back to the last Portal-only release. An app-only rollback does not restore DNS and would leave the newly pointed public hostname unavailable. Never restore the database merely to reverse a DNS/application change.

## Completed cutover — 2026-09-19 UTC

Sam saved both DNS changes. The active release is `guten-public-20260919-01`, prepared from operations commit `5309d3a`, using the previously verified pinned images. Deployment completed successfully. Authoritative DNS resolves both public names to the app host; the five MX records and one TXT record match the saved pre-cutover baseline.

Public browser acceptance passed over normal HTTPS: landing-page redirect, canonical URL, both images, menu navigation, direct reload, publication isolation, and editorial API rejection. HTTP and www redirects preserve the page path. Portal's sign-in page returns 200 and its unauthenticated editorial API returns 401. All three hostnames have trusted Let's Encrypt certificates and negotiated TLS 1.3. The public landing screenshot was visually checked; user visual acceptance is pending.

Evidence is retained locally under ignored `artifacts/`:

- `guten-public-browser-20260919/` — results and screenshot.
- `guten-public-tls-20260919.json` — public certificate metadata.
- `guten-public-deployment-20260919.log` — successful deployment.
- `guten-dns-after-cutover-20260919.json` and `guten-email-dns-baseline-20260919.json` — DNS evidence.

The two temporary preview containers were removed and the SSH preview tunnel stopped. All seven production containers remain running; only Caddy publishes host ports 80/443. No additional AWS resources were created for this cutover. The old Pages project remains available for rollback, and other publication domains remain unchanged.

To repeat the read-only public acceptance check from this repository, choose a new output directory:

```bash
PLAYWRIGHT_CHANNEL=chrome GUTEN_PUBLIC_ARTIFACTS=artifacts/guten-public-recheck node scripts/test_public_site.mjs
```

## Content master

This change serves the cloud copy of published Guten content. It does not make AWS the editing master automatically. Continue view-only acceptance until the content-master switch and any final data reconciliation are explicitly completed.
