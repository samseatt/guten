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
