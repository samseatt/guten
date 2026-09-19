# Referenced media for the first cloud release

Media stays outside container images. Both frontends will mount the same `/srv/guten/assets` directory read-only. This initial deployment uses the app host's disk; it does not require a new S3 image bucket or change content URLs. The existing S3 bucket is reserved for database backups. Keep the original image archive separately.

From the operations repository, with local PostgreSQL running and editorial changes paused:

```bash
python3 scripts/package_media.py \
  --report artifacts/media-review.json
```

The script reads `draft` and `published` in `guten_datalake`, excluding user records. It scans image fields and embedded `/assets/` references in stored content, includes `default.png`, and hashes selected files. External URLs are not fetched. Report locations identify the source rows without copying full content. Bare relative image fields are reported separately because their intended filesystem paths are ambiguous. Domain entries come from published site records and require review before DNS configuration.

To package after reviewing that inventory, use new output filenames:

```bash
python3 scripts/package_media.py \
  --report artifacts/media-release.json \
  --bundle artifacts/media-release.tar
```

A bundle contains `assets/` plus `media-manifest.json`. Missing files stop packaging unless every missing path is explicitly acknowledged with a repeated `--allow-missing PATH` argument. This exception preserves a known existing content defect; it does not repair it. Unsafe paths cannot be acknowledged. Changed source files, escaping paths and final symlinks are rejected; archive contents are verified against the inventory before the completed tar becomes visible. Do not modify the source tree during packaging. Existing output files are never overwritten. No source images or database records are changed or deleted.

## Initial inventory, September 18, 2026

The UTC-dated local artifacts are `artifacts/media-20260919-reviewed.json` and `artifacts/media-20260919.tar` (gitignored). The source contains 2,935 files totaling 4,269,241,361 bytes; 301 referenced files total 407,533,521 bytes, about 90% less. Both draft and published references are retained.

One known missing file, `neubank.ico`, is referenced by both copies of the Neubank site. The initial bundle explicitly acknowledges this missing favicon. Relative favicon values such as `favicon.ico` remain listed for later review; no replacement artwork or database edits were made. Sam confirmed that Glia uses `glia.cash`. The deployment manifest `deploy/domains.initial.json` uses that correction; the original database value `glia.cas` remains unchanged. This manifest lists the 34 stored site domains plus Portal, without assuming `www` aliases. Review domain ownership/DNS before activating it.

Initial tar SHA256: `805cf186e13285efb280b7b6b25cd847da636859a2b3bf6c172897fc88ab4d89`.

Before host installation, verify the tar checksum and per-file manifest in a new staging directory, then install with root ownership and file mode 0644. Do not extract an untrusted archive as root. Keep prior media available when coordinating application rollback; the application release controller does not roll media back. The initial bundle was subsequently verified and installed on the app host; see [app-host bootstrap](cloud-app-bootstrap.md).

Run the synthetic path, selection, missing-file and archive-integrity tests with:

```bash
python3 -B -m unittest discover -s tests -p test_media.py -v
```
