# Batch 4: five parked domains

Prepared September 19, 2026. Cumulative manifest deploy/domains.batch4.json preserves the ten live publications and adds kausar.life → kausar, moxaic.xyz → moxaic, neuconomy.com → neuconomy, neufacture.com → neufacture, neumm.us → neumm. Each www alias redirects to the root.

Sam confirmed all five original Namecheap records: www CNAME to parkingpage.namecheap.com, TTL 30 minutes; @ Unmasked URL Redirect to http://www.<domain>/. Restore those exact types/values for a DNS rollback, not the observed forwarding-service IPs. Keep BasicDNS and unrelated records. The desired website records are A @ → 52.54.75.169 and CNAME www → the domain root, TTL Automatic.

Authoritative pre-change evidence is artifacts/batch4-dns-before.json. Timed-out queries were retried against the second Namecheap authoritative server and preserved alongside the initial failures; all final answers succeeded.

Private AWS browser checks passed for all five: landing, images, canonical URL, navigation/reload and site/editorial API isolation. Kausar and Neufacture initially encountered Playwright route.fulfill “Route is already handled” errors during navigation/cleanup; independent sequential reruns passed without changing assertions. Treat that as an unresolved intermittent preview-transport issue rather than a proven code fix. Evidence: artifacts/batch4-preview-*/, including the two -recheck directories. The previously recorded intermittent application canonical-tag issue remains open; this batch did not reproduce it.

DNS change and public activation pending. Run public HTTPS acceptance for the new domains and regression checks on existing publications/Portal after DNS confirmation. This release reuses current image digests and makes no database or infrastructure changes. AWS remains the content master; registrar transfers and future AI/email work remain separate.
