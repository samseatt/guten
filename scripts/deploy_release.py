#!/usr/bin/env python3
"""App-host deployment/rollback. Never builds images, migrates or restores databases."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

STATE = Path('/var/lib/guten/deployments')
RELEASES = Path('/opt/guten/releases')
APPS = ('datalake','crust','portal','sites')


def verify(bundle):
    manifest=json.loads((bundle/'release.json').read_text())
    if manifest.get('format') != 1 or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',manifest.get('release','')):
        raise ValueError('Unsupported release manifest.')
    expected={'compose.json','deploy_release.py','gateway/Caddyfile','gateway/nginx.conf','gateway/domains.json'}
    if set(manifest['files']) != expected:
        raise ValueError('Unexpected release file inventory.')
    for name,digest in manifest['files'].items():
        path=bundle/name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Release file checksum failed: '+name)
    config=json.loads((bundle/'compose.json').read_text())
    if set(config['services']) != {*APPS,'auth','web','caddy'}:
        raise ValueError('Unexpected service inventory.')
    if {k:v['image'] for k,v in config['services'].items()} != manifest['images']:
        raise ValueError('Image manifest and Compose configuration disagree.')
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9./:_-]*@sha256:[a-f0-9]{64}',image) for image in manifest['images'].values()):
        raise ValueError('Mutable image reference refused.')
    if any('build' in v for v in config['services'].values()): raise ValueError('Host-side builds are forbidden.')
    return manifest


def command(args, **kwargs):
    return subprocess.run(args,check=True,**kwargs)


def compose(bundle,*args,**kwargs):
    return command(['docker','compose','-p','guten-prod','-f',str(bundle/'compose.json'),*args],**kwargs)


def preflight(bundle, manifest):
    # Pull and compare provenance before replacing any application services.
    compose(bundle,'pull')
    for service in APPS:
        output=command(['docker','image','inspect',manifest['images'][service]],capture_output=True,text=True)
        image=json.loads(output.stdout)[0]
        if image.get('Os')!='linux' or image.get('Architecture')!='amd64':
            raise ValueError('Expected linux/amd64 image: '+service)
        label=(image.get('Config',{}).get('Labels') or {}).get('org.opencontainers.image.revision')
        if label!=manifest['source_commits']['guten-'+service]:
            raise ValueError('Image source revision does not match release: '+service)
    # The candidate app's own verified TLS configuration is used for a read-only check.
    probe="""import asyncio,json,sys
from sqlalchemy import text
from app.database import engine
async def check():
 async with engine.begin() as c:
  await c.execute(text('SET TRANSACTION READ ONLY'))
  await c.execute(text("SET LOCAL statement_timeout = '10s'"))
  actual=dict((await c.execute(text('SELECT version,sha256 FROM workflow.schema_migrations'))).all())
  if actual != json.loads(sys.argv[1]): raise RuntimeError('Database migration contract differs; deployment/rollback refused. Run an explicitly reviewed migration separately.')
 await engine.dispose()
asyncio.run(check())
"""
    compose(bundle,'run','--rm','-T','--no-deps','--entrypoint','python','datalake','-B','-c',probe,json.dumps(manifest['migrations']))


def smoke(urls):
    for url in urls:
        if not url.startswith('https://'): raise ValueError('Smoke probes require HTTPS.')
        for attempt in range(6):
            try:
                with urllib.request.urlopen(url,timeout=10) as response:
                    if response.status!=200 or response.url!=url:
                        raise ValueError('Unexpected response/redirect for '+url)
                break
            except Exception:
                if attempt==5: raise
                time.sleep(5)


def write_state(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as stream:
        json.dump(data,stream,indent=2)
        stream.write('\n')
        temporary=Path(stream.name)
    temporary.replace(path)


def apply(bundle,state_dir=STATE):
    state_dir.mkdir(parents=True,exist_ok=True)
    with (state_dir/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state_path=state_dir/'state.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {}
        if bundle is None: bundle=rollback_target(state)
        manifest=verify(bundle)
        if bundle.resolve()!=RELEASES/manifest['release'] or manifest['install_dir']!=str(bundle.resolve()):
            raise ValueError('Install the intact bundle under /opt/guten/releases/<release> before applying.')
        # Failure before preflight completes does not change running services or release state.
        preflight(bundle,manifest)
        old=state.get('last_successful')
        state.update(attempted=manifest['release'],outcome='applying')
        write_state(state_path,state)
        try:
            compose(bundle,'up','-d','--no-build','--pull','never','--wait','--wait-timeout','180')
            smoke(manifest['smoke_urls'])
        except Exception:
            state['outcome']='failed'
            write_state(state_path,state)
            raise RuntimeError('Deployment did not pass readiness. Inspect Compose logs and run rollback; database and persistent volumes were not rolled back.') from None
        if old!=manifest['release']: state['previous']=old
        state.update(last_successful=manifest['release'],outcome='healthy')
        write_state(state_path,state)
        print('Healthy release:',manifest['release'])


def rollback_target(state):
    name=state.get('last_successful') if state.get('outcome') in ('failed','applying') else state.get('previous')
    if not name or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',name):
        raise ValueError('No previous successful release is available.')
    return RELEASES/name


if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    for name in ('plan','apply'):
        sub.add_parser(name).add_argument('bundle',type=Path)
    sub.add_parser('rollback')
    sub.add_parser('status')
    a=p.parse_args()
    if a.action=='plan':
        m=verify(a.bundle)
        print(json.dumps({k:m[k] for k in ('release','install_dir','source_commits','images','migrations','smoke_urls')},indent=2))
    elif a.action=='apply': apply(a.bundle)
    elif a.action=='rollback': apply(None)
    else: print((STATE/'state.json').read_text() if (STATE/'state.json').exists() else 'No recorded deployment.')
