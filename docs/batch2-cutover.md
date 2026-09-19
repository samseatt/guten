# Five-domain batch — September 19, 2026

Domains: bigj.org → bigj; c4a.ca → c4a; can-cer.com → cancer; caucer.net → caucer; drx.network → drx. Each www alias redirects to its canonical root. Existing Guten, Neubank and Portal remain configured in deploy/domains.batch2.json.

The user changed Namecheap DNS before requesting activation. All roots resolve to 52.54.75.169; all www records alias their root. The spelling drx.netwwork in the prompt was a typo: the prior approved mapping and updated DNS identify drx.network. No new infrastructure or database changes are required.

Current DNS, nameservers, mail forwarding MX and SPF records are captured in ignored artifacts/batch2-dns-observed.json. This is a post-user-edit baseline, not proof of the prior forwarding configuration. Exact old forwarding settings were not supplied; obtain them from the user if DNS rollback becomes necessary. Application rollback does not undo DNS or restore database content.

Private AWS browser checks passed for all five sites: landing, images, canonical URL, navigation/reload and API isolation. BIGJ, Cancer, Caucer and DRX expose single-page navigation; the test now checks reloads without requiring a nonexistent second page. C4A's cross-page navigation passed. Evidence: artifacts/batch2-verified-*/. Four domain configuration unit tests passed.

Public activation and acceptance pending. After activation, verify trusted HTTPS and www/HTTP redirects for all five and regress Guten, Neubank and Portal. Remove the private preview and tunnel. AWS remains the content master.
