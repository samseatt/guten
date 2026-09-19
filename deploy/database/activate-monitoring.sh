#!/bin/sh
# Run after the monitoring stack grants metric publication permission.
set -eu
[ "$(id -u)" = 0 ]
[ "$(cat /etc/guten/host-role)" = database ]
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d -m 0755 /usr/local/lib/guten
install -m 0644 "$base/backup_health.py" /usr/local/lib/guten/backup_health.py
for unit in guten-backup-health.service guten-backup-health.timer; do
    install -m 0644 "$base/systemd/$unit" "/etc/systemd/system/$unit"
done
systemd-analyze verify /etc/systemd/system/guten-backup-health.service /etc/systemd/system/guten-backup-health.timer
systemctl daemon-reload
systemctl start guten-backup-health.service
systemctl enable --now guten-backup-health.timer
systemctl list-timers guten-backup-health.timer --no-pager
