#!/bin/sh
# Run only after a manual S3 upload/download/independent restore has passed.
# Installs the sibling systemd unit files and verifies a real job before scheduling.
set -eu
[ "$(id -u)" = 0 ]
[ "$(cat /etc/guten/host-role)" = database ]
[ "$(stat -c '%a:%u' /etc/guten/secrets/backup_aws)" = 600:0 ]
test -f /etc/guten/database/compose.upload.yaml
grep -q '^age1' /etc/guten/database/recipients.txt
if grep -q 'AGE-SECRET-KEY' /etc/guten/database/recipients.txt; then
    echo 'Private recovery identity must not be on the server.' >&2; exit 1
fi
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d -m 0755 /usr/local/lib/guten
install -m 0644 "$base/backup_health.py" /usr/local/lib/guten/backup_health.py
install -m 0644 "$base/prune_backups.py" /usr/local/lib/guten/prune_backups.py
install -m 0644 "$base/systemd/guten-backup.service" /etc/systemd/system/guten-backup.service
install -m 0644 "$base/systemd/guten-backup.timer" /etc/systemd/system/guten-backup.timer
systemd-analyze verify /etc/systemd/system/guten-backup.service /etc/systemd/system/guten-backup.timer
systemctl daemon-reload
systemctl start guten-backup.service
systemctl enable --now guten-backup.timer
systemctl show guten-backup.service -p Result -p ExecMainStatus
systemctl list-timers guten-backup.timer --no-pager
