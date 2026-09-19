#!/bin/sh
# Restore a verified native backup to a NEW staging database; never promote it here.
set -eu
[ "$(id -u)" = 0 ]
[ "$(cat /etc/guten/host-role)" = database ]
[ "$#" = 2 ] || { echo 'Usage: import-native.sh ARCHIVE_DIRECTORY guten_restore_NAME' >&2; exit 1; }
archive=$1
target=$2
case "$target" in guten_restore_?*) ;; *) echo 'A staging database name is required.' >&2; exit 1;; esac
case "$target" in *[!a-z0-9_]*) echo 'Use lowercase letters, digits and underscores.' >&2; exit 1;; esac
[ "${#target}" -le 63 ]
[ ! -e "$archive/INCOMPLETE" ]
cd "$archive"
# Verify only full.dump: schema/data text exports need not be transferred.
python3 - <<'PY'
import hashlib
from pathlib import Path
entries=[line.split()[0] for line in Path('SHA256SUMS').read_text().splitlines() if line.endswith('  full.dump')]
if len(entries)!=1 or hashlib.sha256(Path('full.dump').read_bytes()).hexdigest()!=entries[0]:
    raise SystemExit('Missing/invalid full.dump checksum')
print('Dump checksum verified.')
PY
# createdb refuses an existing target; no drop/overwrite operation is provided.
docker exec -u postgres guten-cloud-db-postgres-1 createdb -T template0 "$target"
docker exec -i -u postgres guten-cloud-db-postgres-1 pg_restore --single-transaction --exit-on-error --no-owner --no-privileges --no-tablespaces -d "$target" < full.dump
echo 'Staging restore complete. Compare fingerprints before any separate promotion.'
