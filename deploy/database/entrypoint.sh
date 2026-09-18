#!/bin/sh
set -eu
# Compose file secrets preserve host ownership. Copy only the server key into
# container runtime storage with PostgreSQL's required ownership and permissions.
install -d -m 700 -o postgres -g postgres /run/guten-tls
install -m 600 -o postgres -g postgres /run/secrets/server_key /run/guten-tls/server.key
exec /usr/local/bin/docker-entrypoint.sh "$@"
