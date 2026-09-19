#!/bin/sh
# Run as root; stdin is a trusted archive of configure_database.py's runtime/ ONLY.
set -eu
[ "$(id -u)" = 0 ]
[ "$(cat /etc/guten/host-role)" = database ]
[ ! -e /etc/guten/database ] || { echo 'Runtime already exists; refusing replacement.' >&2; exit 1; }
install -d -m 0700 /etc/guten/database
# Keep generated modes (public certificates must be container-readable), but do
# not preserve Mac UID 501: libpq rejects a password file owned by another user.
tar --extract --file=- --directory=/etc/guten/database --no-same-owner --same-permissions
chown -R root:root /etc/guten/database
chmod 0700 /etc/guten/database
for name in postgres_password admin_pgpass pgpass database_url server.key bootstrap-roles.sql; do
    test -f "/etc/guten/database/$name"
    chmod 0600 "/etc/guten/database/$name"
done
