# Batch 6: Physx, Xfin, Xgaia, Xjur and Xmos

Prepared September 19, 2026. deploy/domains.batch6.json preserves the twenty live publication sites and adds physx.info → physx, xfin.dev → xfin, xgaia.org → xgaia, xjur.is → xjur, xmos.info → xmos, with www aliases redirecting to each root.

Authoritative pre-change DNS evidence: artifacts/batch6-dns-before.json. Current website records resolve to Namecheap forwarding/parking. A timed-out Xfin CAA query was resolved by a successful authoritative TCP query with no CAA answer (artifacts/batch6-xfin-caa-recheck.txt). Sam confirmed all five exact console records before edits: www CNAME parkingpage.namecheap.com, 30 minutes, and @ Unmasked redirect to http://www.<domain>/.

Private AWS browser checks passed for all five without retry: landing, images, canonical uniqueness and value, navigation/reload, editorial and cross-publication API isolation, including spoofed headers. Evidence: artifacts/batch6-preview-*/. Four domain-configuration tests passed. Existing intermittent canonical/preview-routing issues did not reproduce and are not claimed fixed.

Desired website records after preparation: A @ → 52.54.75.169 and CNAME www → each root, TTL Automatic. Keep BasicDNS and unrelated records. For rollback, restore exact old redirect/CNAME values, not forwarding-service IPs. Public activation awaits DNS confirmation. Apply only this scoped release; verify HTTPS, HTTP/www redirects and public pages, then ask for user iPhone acceptance. No new infrastructure or database changes are needed.

After this batch the nine remaining domains are adaprise.com, convergent.life, ineural.net, neuverse.space, sysb.io, tiers.ai, xmed.ai, xnome.net and xtack.com. Domain-provider/registration prerequisites remain as previously documented.

Release guten-batch6-20260919-01 is staged and passed host bundle verification. The private preview containers and tunnel were removed. DNS change instructions may now be given.

## Activation result

Although Sam's confirmation said four sites, authoritative checks verified all five roots and www aliases were correctly updated. Release guten-batch6-20260919-01 applied successfully. Twenty-five publication sites plus Portal are configured. Evidence: artifacts/batch6-dns-after-check.json, batch6-deployment.log and batch6-final-containers.txt.

All ten new root/www hostnames have trusted Let's Encrypt certificates. Direct AWS browser checks passed landing, images, canonical uniqueness/values, navigation/reload, spoofed-header API isolation, and path-preserving HTTP/www redirects for all five. Hostname resolution was explicitly directed to the AWS IP; normal TLS verification remained enabled and no system DNS configuration changed. Evidence: artifacts/batch6-origin-results.json, batch6-origin-tls.json, batch6-origin-*.png and batch6-origin-check.mjs.

The Mac resolver still returned the five old Namecheap forwarding addresses (artifacts/batch6-mac-resolver.json), so normal local-DNS acceptance for these new names awaits cache convergence. Ordinary public-DNS tests passed for Guten and Neubank, including Portal authentication checks (artifacts/batch6-public-*/). User iPhone acceptance is pending. The earlier intermittent canonical issue did not reproduce and remains an open follow-up.

No conflicting root AAAA or CAA was observed on the successful TCP rechecks after an initial UDP timeout. Evidence: artifacts/batch6-dns-tls-prerequisites.json. No new infrastructure, database changes or mail-record edits occurred in this activation. Private preview resources were removed during preparation.

Sam confirmed iPhone visual acceptance for all five domains and pushed f10432a.
