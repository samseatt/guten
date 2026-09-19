#!/bin/sh
# Feed a reviewed configure_host_firewall.py output to stdin; run as root.
set -eu
[ "$(id -u)" = 0 ]
case "$(cat /etc/guten/host-role)" in application|database) ;; *) exit 1;; esac
install -d -m 0755 /usr/local/lib/guten /etc/systemd/system/docker.service.d
candidate=$(mktemp /usr/local/lib/guten/firewall.XXXXXX)
trap 'rm -f "$candidate"' EXIT
cat > "$candidate"
sh -n "$candidate"
chmod 0700 "$candidate"
# Apply first; only install persistent hook after successful application.
sh "$candidate"
mv "$candidate" /usr/local/lib/guten/firewall.sh
cat > /etc/systemd/system/docker.service.d/guten-firewall.conf <<'UNIT'
[Service]
ExecStartPre=/usr/local/lib/guten/firewall.sh
ExecStartPost=/usr/local/lib/guten/firewall.sh
UNIT
systemctl daemon-reload
