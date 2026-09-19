# Batch 4: five parked domains

Prepared September 19, 2026. Cumulative manifest deploy/domains.batch4.json preserves the ten live publications and adds kausar.life → kausar, moxaic.xyz → moxaic, neuconomy.com → neuconomy, neufacture.com → neufacture, neumm.us → neumm. Each www alias redirects to the root.

Sam confirmed all five original Namecheap records: www CNAME to parkingpage.namecheap.com, TTL 30 minutes; @ Unmasked URL Redirect to http://www.<domain>/. Restore those exact types/values for a DNS rollback, not the observed forwarding-service IPs. Keep BasicDNS and unrelated records. The desired website records are A @ → 52.54.75.169 and CNAME www → the domain root, TTL Automatic.

Authoritative pre-change evidence is artifacts/batch4-dns-before.json. Timed-out queries were retried against the second Namecheap authoritative server and preserved alongside the initial failures; all final answers succeeded.

Private AWS browser checks passed for all five: landing, images, canonical URL, navigation/reload and site/editorial API isolation. Kausar and Neufacture initially encountered Playwright route.fulfill “Route is already handled” errors during navigation/cleanup; independent sequential reruns passed without changing assertions. Treat that as an unresolved intermittent preview-transport issue rather than a proven code fix. Evidence: artifacts/batch4-preview-*/, including the two -recheck directories. The previously recorded intermittent application canonical-tag issue remains open; this batch did not reproduce it.

DNS change and public activation pending. Run public HTTPS acceptance for the new domains and regression checks on existing publications/Portal after DNS confirmation. This release reuses current image digests and makes no database or infrastructure changes. AWS remains the content master; registrar transfers and future AI/email work remain separate.

## Activation result

Sam saved all five records. Authoritative A/www checks passed and guten-batch4-20260919-01 deployed successfully. No conflicting root AAAA or CAA records were observed. Fifteen publication domains plus Portal are now configured. Evidence: artifacts/batch4-dns-after.json, batch4-dns-tls-prerequisites.json, batch4-deployment.log and batch4-final-containers.txt.

All ten new root/www names have trusted Let's Encrypt certificates. Chrome with hostname resolution explicitly directed to the AWS IP passed pages, images, canonical uniqueness/values, navigation or single-page reload, cross-site/editorial API isolation with spoofed headers, and HTTP/www redirects preserving paths. TLS verification stayed enabled; no machine DNS settings were changed. Evidence: artifacts/batch4-origin-results.json, batch4-origin-tls.json, batch4-origin-*.png, and the retained artifacts/batch4-origin-check.mjs verification script.

Normal public-DNS browser regression passed for Guten and Neubank, including Portal sign-in/API authentication checks. The Mac resolver still returned the five original Namecheap IPs and the five unpinned tests timed out; they are not reported as successful normal-DNS checks. Repeat after cache expiry. User iPhone acceptance is pending. No new canonical issue occurred in the successful direct AWS runs; the previously observed intermittent metadata issue remains open.

No database changes or new AWS resources were needed. No preview containers or SSH preview tunnel remain from preparation. Existing mail records were not altered in this activation.

Sam confirmed iPhone visual acceptance for all five batch-4 domains and pushed b67c97b. This closes user visual acceptance; the recorded normal Mac DNS test gap can be rechecked during subsequent rollout.
