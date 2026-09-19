#!/usr/bin/env python3
"""Publish or retry an existing image build record without rebuilding source."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from package_release import APPS


def inspect(tag):
    return json.loads(subprocess.check_output(['docker','image','inspect',tag],text=True))[0]


def save(path,record):
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.build-record-',delete=False) as stream:
        temporary=Path(stream.name)
        json.dump(record,stream,indent=2);stream.write('\n')
    try:os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def publish(path):
    path=Path(path)
    record=json.loads(path.read_text())
    if record.get('platform')!='linux/amd64' or set(record.get('images',{}))!=set(APPS):
        raise ValueError('Expected four Linux amd64 app images')
    # Verify the entire set before any upload. Tags alone are mutable.
    for name,entry in record['images'].items():
        revision=record['source_commits']['guten-'+name]
        if not re.fullmatch('[0-9a-f]{40}',revision) or entry['source_commit']!=revision:
            raise ValueError('Source commit mismatch: '+name)
        if not re.fullmatch(r'[a-z0-9][a-z0-9./_-]*/guten-'+name+':'+revision,entry['tag']):
            raise ValueError('Unexpected image tag: '+name)
        local=inspect(entry['tag'])
        if (local['Id']!=entry['image_id'] or local['Os']!='linux' or local['Architecture']!='amd64' or
            (local['Config'].get('Labels') or {}).get('org.opencontainers.image.revision')!=revision):
            raise ValueError('Local image differs from build record: '+name)
    for name,entry in record['images'].items():
        # Re-pushing is idempotent, including a retry after an uncertain registry result.
        subprocess.run(['docker','push',entry['tag']],check=True)
        repository=entry['tag'].rsplit(':',1)[0]
        digests=[v for v in inspect(entry['tag']).get('RepoDigests',[]) if v.startswith(repository+'@sha256:')]
        if len(digests)!=1:raise ValueError('Cannot identify published digest: '+name)
        entry['digest']=digests[0]
        save(path,record)
    print('Published build record:',path)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record',type=Path)
    publish(parser.parse_args().record)
