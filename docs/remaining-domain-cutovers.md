# Remaining domain cutovers — September 19, 2026

Seven public sites plus Portal are live. Sam visually accepted all five sites from batch 2 and pushed both commits. The original manifest has 27 publication domains still to cut over.

## Next release

The next cumulative manifest, deploy/domains.batch3.json, adds only adama.cc (adama), see-eight.com (c8), and glia.cash (glia), each with its www alias redirecting to the root. Private AWS browser acceptance passed for landing, images, canonical URL, navigation/reload and publication isolation. Evidence: artifacts/batch3-preview-adama/, batch3-preview-c8/, batch3-preview-glia/.

Await the user's exact Namecheap @/www forwarding values before changing DNS. The desired final records are A @ → 52.54.75.169 and CNAME www → the domain root, keeping existing nameservers and mail records. This is a prepared release, not yet live. Do not activate until DNS and certificate prerequisites are checked.

## Inventory and exceptions

Full pre-change observations, including NS, A, AAAA, MX, TXT, CAA and www records, are saved in artifacts/remaining-dns-before-20260919.json. Per-query exit codes and diagnostics are retained: an empty result is not proof that no record exists. A failed initial inventory was rerun with diagnostic preservation.

- Cloudflare nameservers: tiers.ai, xmed.ai, neuverse.space. Obtain underlying record targets/proxy status from the console because public DNS obscures proxied origins. Handle these separately.
- GoDaddy nameservers: ineural.net, sysb.io. The registrar of record is not established solely by nameservers; use the user's account confirmation for administration.
- DNS failures: adaprise.com, convergent.life, omics.cc, xtack.com. Cross-resolver queries returned SERVFAIL/refused authoritative answers (one omics query timed out). See artifacts/remaining-dns-exceptions.json. Verify ownership, spelling, active registration and DNS delegation with the user before including these in a release. No expired/unowned status is inferred from SERVFAIL.
- Other remaining domains returned Namecheap nameservers and parking/forwarding answers. Record exact console URL Redirect targets before replacing those records; public A addresses alone do not preserve forwarding configuration.

Adaprise and Convergent content also passed private preview tests, but their domains were excluded from batch 3 due to DNS failures. No domain mapping is silently renamed. Existing media/content is unchanged and AWS remains the master.

The rollout continues in small batches after user DNS confirmation and public acceptance. A release adds only ready domains; an application rollback does not undo DNS or content. No new paid AWS resources are needed for these hostname additions.

## User corrections and next actions

Sam confirmed the exact pre-change records for adama.cc, see-eight.com and glia.cash: www CNAME parkingpage.namecheap.com., TTL 30 minutes; @ Unmasked URL Redirect to http://www.<domain>/, no TTL displayed. The three-site release is staged and verified; DNS updates have been requested but not yet confirmed.

Adaprise is still registered at GoDaddy and the user plans a transfer to Namecheap. Do not activate it until working DNS points to AWS; registration transfer alone does not provide DNS readiness. Ineural and Sysb are registered at Namecheap but retained GoDaddy nameservers. Convergent and Xtack also retained domaincontrol.com nameservers. The user switched Sysb to BasicDNS; no stock records appeared, consistent with records not being automatically copied between DNS providers.

Ineural still advertises MX 0 smtp.secureserver.net and MX 10 mailstore1.secureserver.net. Ask whether mail or other services are used before changing its nameservers; public DNS cannot enumerate every subdomain/verification record. Convergent and Xtack SERVFAIL answers do not prove absence of mail. The user has been asked about service use before further nameserver changes. Evidence: artifacts/nameserver-transition-checks.json.

The correct Omix domain is omix.cc, confirmed by the user and resolving to Namecheap parking/mail DNS. The future initial manifest was corrected. Before the requested live correction, encrypted backup guten_20260919T154431Z_3lf9pe17 completed successfully. scripts/data-corrections/20260919_omix_domain.sql transactionally corrected only draft.sites and published.sites rows id 48/name omix from omics.cc to omix.cc, with updated_at timestamps. It guards the database name and exact prior values and refuses reruns after correction. No pages were republished and no other content changed. Verification output: artifacts/omix-domain-correction.log. The native Mac development snapshot was intentionally not updated; cloud is authoritative. Existing immutable release bundles remain untouched.

## Mail and future-scope clarification

Sam explicitly confirmed that none of the legacy mail records need preservation. Adaprise's former DiscountASP.NET mail service is also unused and may be discarded. For forthcoming DNS-provider moves, recreate the website records without copying obsolete MX/SPF solely for historical reasons. This does not request mass deletion from unrelated zones during the current batch.

Future idea only: receive mail across the publication domains and provide summaries/agent-assisted handling. No email service, inbound receiver, sending infrastructure, or database changes are authorized by that idea alone; evaluate separately after the website deployment.

## Batch 3 activated

Sam saved DNS changes for adama.cc, see-eight.com and glia.cash. Authoritative A records and www aliases were verified before applying guten-batch3-20260919-01. Deployment completed successfully; all six root/www hostnames have trusted Let's Encrypt certificates. Evidence: artifacts/batch3-deployment.log and batch3-tls.json.

Public browser checks passed for See Eight, Glia, Guten and Neubank, including Portal authentication checks. Adama's first public run failed because two canonical tags persisted beyond five seconds after the client-side landing redirect; an independent rerun passed all assertions. This is an intermittent metadata defect, not established as fixed. Existing root-layout metadata uses request-path headers and the landing component navigates client-side; inspect that interaction in a focused follow-up rather than suppress uniqueness checks. Browser evidence: artifacts/batch3-public-*/ and batch3-public-adama-recheck/. User iPhone acceptance is pending.

Ten publication domains plus Portal are now live. The next release should start from deploy/domains.batch3.json. No new infrastructure, DNS mail cleanup, or database changes occurred in this activation. The old mail-record disposal authorization above applies to future DNS-provider transitions, not an email-service implementation.
