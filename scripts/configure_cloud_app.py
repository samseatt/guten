#!/usr/bin/env python3
"""Prepare production secret files or install validated credentials over pinned SSH."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tomllib
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'.cloud-app'
AUTH_FILES=('oauth2-proxy.cfg','github_client_secret','oauth_cookie_secret')


def prepare(state=STATE):
    state.mkdir(mode=0o700,exist_ok=True);state.chmod(0o700)
    files={'oauth2-proxy.cfg':(ROOT/'deploy/oauth2-proxy.cfg.example').read_text(),'github_client_secret':'REPLACE_GITHUB_CLIENT_SECRET\n','ghcr_read_token':'REPLACE_READ_PACKAGES_TOKEN\n','oauth_cookie_secret':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}
    for name,value in files.items():
        path=state/name
        if not path.exists():
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(value)
    print('Private production placeholders ready; existing files preserved.')


def read_private(path):
    if path.is_symlink() or path.stat().st_mode & 0o077:raise ValueError('Expected private regular file: '+path.name)
    return path.read_text()


def validate_auth(state=STATE):
    values={name:read_private(state/name) for name in AUTH_FILES}
    config=tomllib.loads(values['oauth2-proxy.cfg'])
    expected=tomllib.loads((ROOT/'deploy/oauth2-proxy.cfg.example').read_text())
    client=config.get('client_id','')
    if not re.fullmatch('[A-Za-z0-9._-]{10,128}',client) or 'REPLACE' in client:raise ValueError('Production Client ID is not configured')
    expected['client_id']=client
    if config!=expected:raise ValueError('OAuth settings differ from the reviewed production template')
    secret=values['github_client_secret'].strip()
    if 'REPLACE' in secret or not re.fullmatch('[A-Za-z0-9_-]{20,256}',secret):raise ValueError('Production Client secret is not configured')
    cookie=values['oauth_cookie_secret'].strip()
    try:decoded=base64.b64decode(cookie,altchars=b'-_',validate=True)
    except ValueError:raise ValueError('Invalid cookie key') from None
    if len(decoded)!=32:raise ValueError('Expected a 32-byte cookie key')
    values['github_client_secret']=secret;values['oauth_cookie_secret']=cookie
    return values


def validate_token(state=STATE):
    token=read_private(state/'ghcr_read_token').strip()
    if 'REPLACE' in token or not re.fullmatch('[A-Za-z0-9_]{20,256}',token):raise ValueError('Pull token is not configured')
    req=urllib.request.Request('https://api.github.com/user',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=20) as response:
        scopes={scope.strip() for scope in response.headers.get('X-OAuth-Scopes','').split(',') if scope.strip()}
        owner=json.load(response)['login']
        expiry=response.headers.get('GitHub-Authentication-Token-Expiration')
    if owner!='samseatt' or scopes!={'read:packages'}:raise ValueError('Expected samseatt token with only read:packages scope')
    return token,{'user':owner,'scopes':sorted(scopes),'expires_at':expiry}


REMOTE_AUTH='''import json,os,pathlib,sys
values=json.load(sys.stdin)
names={'oauth2-proxy.cfg','github_client_secret','oauth_cookie_secret'}
if set(values)!=names:raise SystemExit('Unexpected secret filenames')
root=pathlib.Path('/etc/guten/secrets')
root.mkdir(mode=0o700,parents=True,exist_ok=True)
for name,value in values.items():
    path=root/name
    if path.is_symlink() or (path.exists() and path.read_text()!=value):raise SystemExit('Existing secret differs; deliberate rotation required: '+name)
for name,value in values.items():
    path=root/name
    if not path.exists():
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
        with os.fdopen(fd,'w') as stream:stream.write(value)
    os.chown(path,0,65532);os.chmod(path,0o640)
print('Production OAuth files installed with root ownership and restricted group access.')
'''


def ssh_command(args,command):
    if not re.fullmatch('[a-zA-Z0-9.-]+',args.host):raise ValueError('Invalid host')
    return ['ssh','-F','/dev/null','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(args.known_hosts.resolve()),'-i',str(args.identity.resolve()),'ubuntu@'+args.host,command]


def install(args):
    values=validate_auth(args.state)
    token,metadata=validate_token(args.state)
    subprocess.run(ssh_command(args,'sudo -n python3 -c '+shlex.quote(REMOTE_AUTH)),input=json.dumps(values),text=True,check=True)
    # Dedicated app host: root performs release pulls. Docker stores this read-only
    # registry credential in root's private config; never copy the publishing token.
    command="sudo -n sh -c 'umask 077; mkdir -p /root/.docker; chmod 700 /root/.docker; docker login ghcr.io --username samseatt --password-stdin; result=$?; test ! -f /root/.docker/config.json || chmod 600 /root/.docker/config.json; exit $result'"
    subprocess.run(ssh_command(args,command),input=token+'\n',text=True,check=True)
    print(json.dumps({'registry_access':metadata,'oauth':'installed; real login not yet tested'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','install'))
    p.add_argument('--state',type=Path,default=STATE)
    p.add_argument('--host',default='52.54.75.169')
    p.add_argument('--identity',type=Path,default=ROOT/'.cloud-provision/guten-cloud')
    p.add_argument('--known-hosts',type=Path,default=ROOT/'.cloud-provision/known_hosts')
    args=p.parse_args()
    if args.action=='prepare':prepare(args.state)
    else:install(args)
