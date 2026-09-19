#!/usr/bin/env python3
"""Verify a media bundle and install its first version; never replace active media."""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import tarfile
import tempfile


def sha256(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def install(archive_path,expected,root):
    archive_path=Path(archive_path);root=Path(root)
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise ValueError('Invalid SHA256')
    if sha256(archive_path)!=expected:raise ValueError('Archive checksum mismatch')
    active=root/'assets'
    if os.path.lexists(active):raise ValueError('Active media already exists; explicit replacement procedure required')
    versions=root/'media';versions.mkdir(parents=True,exist_ok=True)
    target=versions/expected
    if target.exists():raise ValueError('Version already exists; inspect it before retrying')
    with tempfile.TemporaryDirectory(prefix='.install-',dir=versions) as temporary:
        staging=Path(temporary)/'version';staging.mkdir(mode=0o755)
        with tarfile.open(archive_path,'r:') as archive:
            members=archive.getmembers()
            names=[m.name for m in members]
            if len(names)!=len(set(names)) or any(not m.isfile() for m in members):raise ValueError('Duplicate or non-file archive member')
            member=archive.getmember('media-manifest.json')
            if member.size>16*1024*1024:raise ValueError('Oversized manifest')
            with archive.extractfile(member) as stream:report=json.load(stream)
            if report.get('format')!=1 or report.get('invalid'):raise ValueError('Unsafe or unsupported manifest')
            entries=report['files']
            paths=[entry['path'] for entry in entries]
            if len(paths)!=len(set(paths)):raise ValueError('Duplicate inventory path')
            if set(names)!={'media-manifest.json',*('assets/'+p for p in paths)}:raise ValueError('Archive and inventory differ')
            for entry in entries:
                relative=entry['path'];parts=relative.split('/')
                if not relative or any(p in ('','..','.') for p in parts) or '\\' in relative or '\x00' in relative or PurePosixPath(relative).is_absolute():raise ValueError('Unsafe inventory path')
                member=archive.getmember('assets/'+relative)
                if member.size!=entry['bytes']:raise ValueError('Size mismatch')
                dest=staging/'assets'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as source,dest.open('xb') as output:shutil.copyfileobj(source,output)
                if sha256(dest)!=entry['sha256']:raise ValueError('Media checksum mismatch')
                dest.chmod(0o644)
            (staging/'media-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
            for path in staging.rglob('*'):
                if path.is_dir():path.chmod(0o755)
            (staging/'media-manifest.json').chmod(0o644)
        # Detect archive mutation during the copy as well as before it.
        if sha256(archive_path)!=expected:raise ValueError('Archive changed during installation')
        staging.rename(target)
    root.chmod(0o755);versions.chmod(0o755)
    # Exclusive creation: a concurrent active link is never overwritten.
    active.symlink_to('media/'+expected+'/assets',target_is_directory=True)
    return {'archive_sha256':expected,'version':str(target),'files':len(entries),'missing':report['missing'],'active':str(active)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--root',type=Path,default=Path('/srv/guten'))
    a=p.parse_args();print(json.dumps(install(a.archive,a.sha256,a.root),indent=2))
