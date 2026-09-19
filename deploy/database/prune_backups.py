#!/usr/bin/env python3
"""Conservative local retention; default is a dry run. Never removes unuploaded backups."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
from backup_health import uploaded


def candidates(root,now):
    archives=uploaded(root)
    # Do not prune while uploads have been stale for more than 30 hours.
    if not archives or not 0 <= (now-archives[0][0]).total_seconds() <= 30*3600:return []
    return [entry for entry in archives[7:] if entry[0]<now-timedelta(days=30)]


def prune(root,now,apply=False):
    selected=[]
    for created,path,meta in candidates(root,now):
        # Validate ciphertext before deleting this local recovery copy.
        with (path/'full.dump.age').open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=meta['sha256']:continue
        selected.append(path.name)
        if apply:
            # Only the three validated known regular files; no recursive deletion.
            for name in ('UPLOADED','manifest.json','full.dump.age'):(path/name).unlink()
            path.rmdir()
    return selected


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/etc/guten/database/backups'))
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    if a.root.is_symlink():p.error('Backup root cannot be a symlink')
    print(json.dumps({'applied':a.apply,'selected':prune(a.root,datetime.now(timezone.utc),a.apply)}))
