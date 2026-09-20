# Production content master

Effective September 19, 2026 UTC, AWS `guten_datalake` on `guten-db-01` is the authoritative Guten content database. Use https://portal.guten.ink/dashboard for real content edits and publishing. This follows Sam's successful public-site acceptance and instruction to proceed with the next task.

## What changed

The cloud database was already serving Portal and the public Guten site. No further import, schema migration, content mutation, or application reconfiguration was needed. This is an operational handover: future cloud edits are authoritative. Draft and published remain separate; saving a draft does not publish it.

The native Mac `guten_datalake` is now a development/reference snapshot. Local edits are not synchronized to AWS. Do not edit localhost expecting the public site to change. Use disposable restored databases for development and migration rehearsals. Existing local applications are not technically write-disabled; this boundary is operational, not a database permission change. Shared PostgreSQL and VitalEdge databases were left untouched.

## Cutover evidence

Read-only comparison while editing was paused verified all 19 table contents/row counts, 17 sequence states, 125 column definitions, and 32 indexes against the Mac. Cloud fingerprints also exactly match the independently restored and verified bootstrap baseline. Five CHECK definitions differ only in the previously reviewed PostgreSQL 14/17 array/text-cast rendering; allowed values and constraint identities match.

Evidence: ignored `artifacts/master-switch-native.json` and `artifacts/master-switch-cloud.json`. Public browser acceptance passed, and Sam confirmed guten.ink pages/images/links and www redirection.

A normal scheduled backup completed at 03:06 UTC. The additional handover checkpoint `guten_20260919T040509Z_y31ymrvw` completed at 04:05 UTC with `Result=success` and `ExecMainStatus=0`; its UPLOADED receipt points to:

`s3://guten-backups-983732020946-us-east-1/guten/database/guten_20260919T040509Z_y31ymrvw/`

The archive contains encrypted `full.dump.age` and its manifest. Independent recovery was already rehearsed against this exact cloud content/schema baseline; this new checkpoint was uploaded successfully but was not separately restored. See [backup activation](cloud-backup-activation.md) and [monitoring/retention](backup-monitoring-retention.md). Keep the independently archived offline decryption identity and configuration secrets.

## Editing and deployments

- Make real edits in the production Portal. Check View Draft, then publish deliberately and verify View Published.
- All 34 original publication domains and Portal are now live on AWS. New publications need a separate domain activation; follow [the add-a-site cookbook](add-a-site.md).
- Code deployments update containers/configuration, not production content. Never restore the old Mac dump over production as part of a routine deployment.
- Before future migrations, take a cloud backup and rehearse against a restored copy. Refresh development from cloud archives into a new disposable database; do not silently replace the native database or unrelated project databases.
- Media files are still the packaged assets on the application host. Editing text does not upload new images. New media requires the existing deliberate packaging/release process.

## Recovery boundary

Application rollback does not undo content edits or replace the database. Restore encrypted backups into a new isolated `guten_restore_*` database, validate content and schema, then plan any production replacement explicitly. Restoring an older archive loses subsequent edits unless reconciled first. Never solve a failed application release by blindly restoring a database.

To revert the editorial master to the Mac later, first pause cloud editing, export the current cloud data, restore and verify a separate local database, and deliberately switch workflows. The old local snapshot will become stale as soon as production edits begin. DNS rollback to Cloudflare Pages likewise does not move the content master.
