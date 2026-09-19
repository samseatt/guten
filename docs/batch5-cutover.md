# Batch 5: Neurocoin, NGOC8, Nudge, Nudger and Omix

Prepared September 19, 2026. The cumulative deploy/domains.batch5.json preserves the fifteen configured sites and adds neurocoin.cash → neurocoin, ngoc8.com → ngoc8, nudge.ink → nudge, nudger.pro → nudger, omix.cc → omix, each with a www alias redirecting to the canonical root.

Private AWS browser acceptance passed for all five, with unchanged pinned images: landing, two loaded images each, canonical uniqueness and URL, multi-page navigation or single-page reload, editorial/cross-publication API rejection including spoofed headers. Evidence: artifacts/batch5-preview-*/. Four domain-configuration tests passed. Neither previously recorded intermittent metadata nor preview-routing failures appeared in these runs; they are not claimed fixed.

Authoritative DNS baseline is artifacts/batch5-dns-before.json. All final queries succeeded. Neurocoin, NGOC8, Nudge and Nudger still resolve to Namecheap forwarding and www parking CNAMEs. Exact @ URL Redirect targets and www TTL confirmation were requested from the user before edits. Omix already has A @ → 52.54.75.169 and CNAME www → omix.cc; do not ask for redundant Omix DNS changes. The earlier corrected database and domain manifest both use omix.cc; no database changes are needed here.

For the four parked domains, desired website records are A @ → 52.54.75.169 and CNAME www → that domain root, TTL Automatic; preserve BasicDNS and unrelated records. Record exact old forwarding targets for rollback. DNS rollback and application rollback are separate; neither requires a database restore.

Public activation is pending. After DNS confirmation, apply the immutable release, verify certificates and redirects and public browser acceptance, and ask for iPhone verification. Public DNS caches may retain the old forwarding answers. The private preview is removed after preparation; no additional paid infrastructure is needed.

## Activation — September 19, 2026

Sam confirmed the four parked domains had the expected Namecheap www parking CNAME and @ unmasked http://www.<domain>/ redirect records, then saved their A/CNAME changes. Omix was already correctly pointed. Authoritative checks passed for all five before applying guten-batch5-20260919-01. The release completed successfully. Twenty publication sites plus Portal are now configured.

All ten root/www names have trusted Let's Encrypt certificates. Direct AWS browser checks passed pages, images, canonical uniqueness/URLs, navigation/reload, API isolation including spoofed headers and path-preserving HTTP/www redirects. The browser used explicit hostname resolution to the AWS IP while retaining normal certificate verification; no system DNS settings changed. Evidence: artifacts/batch5-origin-results.json, batch5-origin-tls.json, batch5-origin-*.png and retained batch5-origin-check.mjs.

Normal public-DNS tests passed for Omix, Guten and Neubank, including Portal sign-in availability and editorial API authentication. The Mac resolver still returned the old Namecheap addresses for Neurocoin, NGOC8, Nudge and Nudger, so ordinary-DNS verification for those four remains pending cache convergence. User iPhone acceptance is pending. The previous intermittent metadata issue did not reproduce here and remains an open follow-up.

Deployment/DNS evidence: artifacts/batch5-deployment.log, batch5-dns-after.json, batch5-mac-resolver.json, batch5-final-containers.txt, and batch5-public-*/. No new infrastructure, database updates or mail configuration changes were made; private preview/tunnel cleanup was completed before activation.
