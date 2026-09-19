# Backup monitoring and retention

## Approved policy and current state

The user approved local retention of 30 days, always preserving the newest seven successfully uploaded archives; S3 current-object expiration after 180 days and noncurrent-version expiration after another 30 days; failed/unuploaded local archives remain for inspection. SNS email notifications to the supplied address were authorized separately.

Local retention is deployed as an ExecStartPost hook after a successful backup and certificate check. The job uses the same backup lock. All current files are recent: dry-run and real execution selected zero archives for deletion. The local inspector reports healthy backup status and approximately 93% free disk. No cloud alarm or S3 completed-object expiration has been activated yet; the Admin handoff below is pending.

## Monitoring design

One standard-resolution CloudWatch metric (`Guten/Operations`, `BackupHealth`, dimension `Host=guten-db-01`) is published every 15 minutes. One alarm evaluates the maximum in two 15-minute periods, requires both to breach, and treats missing data as breaching. SNS sends ALARM and recovery/OK emails. Missing-heartbeat detection runs in AWS, independently of the database machine.

Metric code 0 is healthy. Other values combine these flags:

| Flag | Condition |
| --- | --- |
| 1 | Last backup service result is not success or is unavailable |
| 2 | No recognized successful upload receipt within 30 hours, or its timestamp is in the future |
| 4 | Less than 15% disk space is free on the backup filesystem |
| 8 | Database certificate expires within 30 days or cannot be checked |

The email's alarm description explains the flags and inspection commands. Detailed reasons remain in the host journal; no database content or secrets are sent as metrics. A crashed monitor, stopped Docker/host, lost network or expired/disabled machine credential prevents publication and eventually triggers the missing-data alarm. CloudWatch uses an extended evaluation range for missing data, so this is not an exact 30-minute outage SLA. It sends state-change notifications, not repeated emails every 15 minutes. It does not guarantee detecting a later deletion of objects from S3: it checks the successful local upload receipt, whose remote recoverability was separately tested.

Expected baseline outside free-tier allowances: approximately USD 0.30/month for one metric plus USD 0.10/month for one standard alarm, with small request/SNS charges additional. No new compute, Lambda, load balancer, CloudWatch Logs ingestion or paid monitoring agent is introduced. Existing account-wide free allowances may reduce charges; there is no hard cost cap.

The existing machine identity receives only `cloudwatch:PutMetricData` constrained to namespace `Guten/Operations`. CloudWatch requires Resource `*` for this API; this does not grant read/admin access or publication to other namespaces. The SNS topic policy permits only the named Guten CloudWatch alarm, from the expected AWS account, to publish notifications.

## Admin CloudShell handoff

Generate a private local handoff file:

```bash
python3 scripts/prepare_backup_operations.py --email YOUR_EMAIL \
  --output .cloud-provision/setup-backup-operations.py
```

The file has already been generated using the authorized address. In Admin CloudShell upload it using Actions > Upload file, then run:

```bash
python3 ~/setup-backup-operations.py
```

This first reads the live `guten-bootstrap` template and changes only `BackupBucket.LifecycleConfiguration`. Existing rules and parameters are preserved. It creates a change set and refuses to execute unless the only change is a nonreplacement modification of the bucket's lifecycle property. Host resources, IPs, SSH launch commands and database volumes are untouched. This avoids an out-of-band lifecycle edit drifting from CloudFormation. An already-configured lifecycle is a no-op.

It then creates the separate `guten-backup-monitoring` stack: SNS topic, email subscription, topic policy, one alarm, and one scoped IAM inline policy attached to the existing upload user. The launcher checks the Admin identity/account and refuses an existing monitoring stack. SNS sends a subscription confirmation email; click its confirmation link. Initial missing-data alarms may occur until the host heartbeat is activated. Do not repeatedly rerun a failed script; inspect the specific stack/change set and retain the error.

After the user reports completion, verify stack status, bucket lifecycle, subscription confirmation and alarm settings, start the heartbeat manually, and enable `guten-backup-health.timer`. `deploy/database/activate-monitoring.sh` is the repeatable host installer. Its unit files and inspector are already staged on the database host, but its timer is not enabled because publication permission is still pending. Finish with an end-to-end alert/recovery test and confirm email receipt before claiming notifications work.

## Retention safeguards

`prune_backups.py` defaults to dry-run. It recognizes only folders containing exactly `full.dump.age`, `manifest.json` and `UPLOADED`, checks the manifest/database/format/timestamp and exact expected S3 destination, rejects symlinks and malformed files, preserves the newest seven recognized uploads, and only considers older-than-30-day candidates. If the latest recognized upload is older than 30 hours, cleanup stops. Each candidate's ciphertext hash must match before deletion. Only the three known regular files and their empty directory are removed; there is no recursive tree deletion.

Upload receipts are operational evidence, not an independent live S3 inventory. Keep doing recovery tests and monitoring S3 configuration. Failed, unuploaded or corrupted local archives are deliberately retained and can eventually consume disk; the disk alert provides visibility and they require manual inspection.

S3 rules apply only to `guten/database/`. Current objects become expired after 180 days; with versioning enabled this creates delete markers, with the noncurrent data then eligible for permanent deletion 30 days later. Overwritten versions are eligible 30 days after becoming noncurrent. A separate scoped rule cleans up expired delete markers once no versions remain. The initial bucket-wide seven-day incomplete-multipart cleanup is preserved. Lifecycle processing is asynchronous, not an exact deletion deadline. No archive storage-class transitions are configured.

If backups stop for many months, S3 lifecycle still advances and can eventually remove all old backups. The seven-copy floor applies locally, not to S3. Preserve deliberate long-term/manual recovery archives separately before pausing or decommissioning the installation. The initial infrastructure bootstrap intentionally starts without completed-object expiry; this separate follow-up introduces retention only after recovery has been tested and the policy approved.

## Tests and evidence

Portable tests cover healthy/failed/stale/low-disk/certificate states, newest-seven preservation, age cutoff, dry-run behavior, damaged and unuploaded archives, symlinks and stale-upload cleanup refusal. A fake AWS CLI test exercises the bucket-only change-set guard and refuses host changes, resource replacement, unrelated property changes and extra resources. Both generated CloudFormation templates pass cfn-lint. Live local checks and the integrated backup/retention job are recorded in `.cloud-provision/backup-health-retention-local.log` and `retention-service-verification.log`.

```bash
python3 -m unittest discover -s tests -p test_backup_operations.py
python3 -m unittest discover -s tests -p test_retention_changeset.py
```

Host inspection:

```bash
sudo python3 /usr/local/lib/guten/backup_health.py
sudo flock -n /run/lock/guten-backup.lock python3 /usr/local/lib/guten/prune_backups.py
sudo journalctl -u guten-backup-health.service -n 30 --no-pager
```

References: [CloudWatch missing data](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html), [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/), [S3 lifecycle and version expiry](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html).
