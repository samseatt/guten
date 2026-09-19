# Batch 6: Physx, Xfin, Xgaia, Xjur and Xmos

Prepared September 19, 2026. deploy/domains.batch6.json preserves the twenty live publication sites and adds physx.info → physx, xfin.dev → xfin, xgaia.org → xgaia, xjur.is → xjur, xmos.info → xmos, with www aliases redirecting to each root.

Authoritative pre-change DNS evidence: artifacts/batch6-dns-before.json. Current website records resolve to Namecheap forwarding/parking. A timed-out Xfin CAA query was resolved by a successful authoritative TCP query with no CAA answer (artifacts/batch6-xfin-caa-recheck.txt). Exact console @ URL Redirect targets and www TTL confirmation were requested from the user before edits; the expected pattern is www CNAME parkingpage.namecheap.com, 30 minutes, and @ Unmasked redirect to http://www.<domain>/.

Private AWS browser checks passed for all five without retry: landing, images, canonical uniqueness and value, navigation/reload, editorial and cross-publication API isolation, including spoofed headers. Evidence: artifacts/batch6-preview-*/. Four domain-configuration tests passed. Existing intermittent canonical/preview-routing issues did not reproduce and are not claimed fixed.

Desired website records after preparation: A @ → 52.54.75.169 and CNAME www → each root, TTL Automatic. Keep BasicDNS and unrelated records. For rollback, restore exact old redirect/CNAME values, not forwarding-service IPs. Public activation awaits DNS confirmation. Apply only this scoped release; verify HTTPS, HTTP/www redirects and public pages, then ask for user iPhone acceptance. No new infrastructure or database changes are needed.

After this batch the nine remaining domains are adaprise.com, convergent.life, ineural.net, neuverse.space, sysb.io, tiers.ai, xmed.ai, xnome.net and xtack.com. Domain-provider/registration prerequisites remain as previously documented.
