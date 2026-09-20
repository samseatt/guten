# Cloudflare publication batch

Prepared September 19, 2026. Candidate deploy/domains.batch8.json preserves the 27 domains configured by batch 7 and adds neuverse.space → neuverse, tiers.ai → tiers and xmed.ai → xmed, each with www redirected to its canonical root.

Sam supplied the exact current records for rollback:

| Domain | Root record | www record | Proxy / TTL |
| --- | --- | --- | --- |
| neuverse.space | CNAME neuverse.pages.dev | CNAME neuverse.pages.dev | Both Proxied / Auto |
| tiers.ai | CNAME tiersai.pages.dev | CNAME tiersai.pages.dev | Both Proxied / Auto |
| xmed.ai | CNAME xmedai.pages.dev | CNAME xmedai.pages.dev | Both Proxied / Auto |

Desired changes for each: root A → 52.54.75.169, DNS only, Auto; www CNAME → its own root, DNS only, Auto. Keep Cloudflare nameservers and unrelated records, and retain all Pages projects for rollback. The user has authorized discarding obsolete email records when necessary, but this cutover does not require deleting them. New Pages aliases/projects are outside scope. Do not delete explicit AAAA records without inspecting them; IPv6 returned for proxied CNAMEs may be Cloudflare-generated rather than an editable record.

All three sites passed private AWS browser acceptance against unchanged production images: landing, images, canonical URLs, navigation/reload and API isolation. Evidence: artifacts/final-nine-preview-neuverse/, final-nine-preview-tiers/ and final-nine-preview-xmed/. DNS snapshot: artifacts/cloudflare-pre-cutover.json. Public activation awaits user DNS edits and authoritative verification. No database changes are needed.

After activation, verify trusted certificates, HTTP/www redirects, content and existing Guten/Portal behavior, then obtain iPhone visual acceptance. DNS rollback means restoring the exact proxied CNAME values above; Pages custom domains may need to reactivate after routing is restored. Application rollback alone does not revert DNS, and DNS rollback does not require restoring a database.

Adaprise's transfer was reported approved/completed by GoDaddy while Namecheap still shows awaiting release. Keep it outside this release until the destination account and authoritative DNS are ready. Convergent, Ineural and Xtack also remain separate.

## Activated September 19, 2026

Sam saved the six website records. Authoritative root A and www CNAME checks passed, with no remaining root/www AAAA addresses. The Mac resolver also pointed all three roots to AWS. Release guten-batch8-20260919-01 applied successfully; thirty publication sites plus Portal are live.

All three sites passed ordinary public-DNS browser acceptance: landing, images, canonical uniqueness/value, navigation/reload, API isolation and path-preserving HTTP/www redirects. Guten and Portal regression checks passed. All six root/www names have trusted Let's Encrypt certificates. Captured MX/TXT values match their pre-cutover baseline. No new infrastructure or database changes were made; Pages projects were retained. User visual acceptance is pending.

Evidence: artifacts/batch8-dns-after.json, batch8-mac-resolver.json, batch8-deployment.log, batch8-public-*/, batch8-tls.json, batch8-mail-dns-check.json, batch8-final-containers.txt. No DNS override was required for these public browser tests. The previous intermittent metadata/preview issues did not reproduce and remain separate follow-ups.

Remaining publication domains: adaprise.com, convergent.life, ineural.net and xtack.com. Keep them excluded until their registration/delegation/website records are ready.

Sam visually confirmed all three Cloudflare domains and pushed eb2c4e6. User acceptance is complete.
