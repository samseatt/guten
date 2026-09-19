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

## Content master

This change serves the cloud copy of published Guten content. It does not make AWS the editing master automatically. Continue view-only acceptance until the content-master switch and any final data reconciliation are explicitly completed.
