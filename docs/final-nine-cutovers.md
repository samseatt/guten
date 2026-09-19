# Final nine publication domains

September 19, 2026 inventory: 25 publication sites plus Portal are live. Sam visually accepted all five batch-6 sites and pushed f10432a.

## Next candidate: Sysb and Xnome

Cumulative deploy/domains.batch7.json adds sysb.io → sysbio and xnome.net → xnome, with www aliases. Both sites passed private AWS browser checks for landing, images, canonical URL/uniqueness, navigation/reload and API isolation. This release is prepared, not activated.

Sysb is delegated to Namecheap BasicDNS; no root A or www record is currently present. The user previously reported an empty Advanced DNS zone after switching nameservers. Xnome remains at Namecheap with root forwarding and www parking CNAME; exact console redirect target/TTL confirmation is requested before DNS edits. Desired records are A @ → 52.54.75.169 and CNAME www → the domain root, TTL Automatic. Do not change nameservers again for these two.

## Other DNS prerequisites

- Adaprise: still SERVFAIL; user-managed registrar transfer and explicit DNS setup pending. Transfer alone does not reset nameservers.
- Convergent and Xtack: still SERVFAIL; Namecheap account holders can deliberately replace obsolete custom delegation with BasicDNS and create website records after confirmation.
- Ineural: still delegated to domaincontrol.com with legacy parking A records; user confirmed old mail records may be discarded. Nameserver change and new website records remain pending.
- Neuverse, Tiers and Xmed: Cloudflare proxied roots. Need console record type, underlying targets, TTL and proxy status for @/www/AAAA before changing them; public DNS does not reveal proxied origin targets.

The user was asked for current administrative status and Cloudflare records. No nameservers, public DNS, database content, or mail records were changed by these preparations. AI/email expansion remains out of scope.

## Evidence

artifacts/final-nine-dns.json records root/www NS, A, AAAA, CNAME, MX, TXT and CAA with query diagnostics. artifacts/batch7-sysb-authoritative.txt and batch7-xnome-authoritative.txt contain additional authoritative checks. Private tests used a temporary loopback-only preview and the current immutable production images, with no public certificates for unready domains.

All nine completed page assertions. Eight exited successfully on the first run; Ineural's first run hit the known preview-route cleanup error after assertions. Its independent rerun passed and is recorded separately. Per-site evidence: artifacts/final-nine-preview-*/ and final-nine-preview-results.json. The known metadata and preview-transport issues remain open; passing these runs does not establish a fix.

## Sysb and Xnome activated

Sam confirmed Namecheap Advanced DNS updates for both domains. Authoritative root A and www CNAME matched AWS before applying guten-batch7-20260919-01. The release succeeded; public DNS browser acceptance passed for both sites plus Guten/Portal regression. Images, canonical URLs, navigation/reload, API isolation and HTTP/www redirects passed. All four new root/www names have trusted Let's Encrypt certificates. User iPhone acceptance is pending.

Evidence: artifacts/batch7-dns-after.json, batch7-deployment.log, batch7-public-*/, batch7-tls.json. Twenty-seven publication sites plus Portal are now live. No database or new infrastructure changes were required. The Cloudflare three-domain release is separately staged and verified at /opt/guten/releases/guten-batch8-20260919-01; its DNS update instructions have been sent, but it is not yet active.

Sam visually accepted Sysb and Xnome on both Mac and iPhone and pushed both related commits. The three Cloudflare domains have now been activated; see cloudflare-publication-cutover.md for verification evidence.
