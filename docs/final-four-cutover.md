# Final four publication domains

Prepared September 19, 2026. deploy/domains.batch9.json preserves the thirty live publications and adds adaprise.com → adaprise, convergent.life → convergent, ineural.net → ineural and xtack.com → xtack, each with www redirected to its root. This completes the original 34-site mapping when activated.

All four passed the prior private AWS content checks using the same pinned application images. Evidence: artifacts/final-nine-preview-adaprise/, final-nine-preview-convergent/, final-nine-preview-ineural-recheck/, final-nine-preview-xtack/. Ineural's initial preview transport cleanup failure and passing independent rerun remain documented; no fix is inferred. Public acceptance still follows DNS readiness.

Current snapshot: artifacts/final-four-dns-before.json. Adaprise now advertises dns1/dns2.registrar-servers.com despite the user's report that Namecheap transfer status is not yet complete. Ineural retains ns15/ns16.domaincontrol.com; Convergent and Xtack still SERVFAIL with their earlier obsolete GoDaddy delegation. No DS records were returned by successful recursive DS queries. Recheck authoritative/root/www readiness before activation.

The user explicitly authorized discarding obsolete hosting and email records, including DiscountASP.NET for Adaprise; there is no requirement to restore those inactive services. For Convergent, Ineural and Xtack select Namecheap BasicDNS under Nameservers, then create A @ → 52.54.75.169 and CNAME www → the domain root under Advanced DNS, TTL Automatic. For Adaprise leave BasicDNS selected and create the same website records when the control panel permits. Do not enter an IP in nameserver fields. A provider switch does not automatically copy old zone records. Do not activate a hostname whose delegation/records remain unready.

Old delegation for historical reference: Convergent ns61/ns62.domaincontrol.com, Ineural ns15/ns16.domaincontrol.com, Xtack ns71/ns72.domaincontrol.com (user supplied). Adaprise's former three DiscountASP nameservers were removed by the user; exact old names were not supplied and no service rollback is desired.

The immutable final release is prepared rather than live. If only three domains become ready, generate a new scoped release excluding the unready one; do not expose incomplete certificate configuration. Code release rollback does not restore DNS or overwrite database content. No new paid infrastructure or database edits are required; all future email/AI work remains out of scope.
