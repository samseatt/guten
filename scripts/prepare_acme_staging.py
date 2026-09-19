#!/usr/bin/env python3
"""Prepare a single-domain ACME rehearsal serving only a maintenance response."""
import argparse
import json
from pathlib import Path
import re
from deploy_release import verify


def prepare(bundle,target):
    manifest=verify(bundle)
    domains=json.loads((bundle/'gateway/domains.json').read_text())
    host=domains['portal']
    if domains.get('portal_only') is not True or domains['sites'] or not re.fullmatch('[a-z0-9.-]+',host):
        raise ValueError('Staging issuance requires the explicit Portal-only release')
    if target.exists():raise ValueError('Output exists')
    target.mkdir(parents=True)
    install=Path('/opt/guten/acme-staging')
    caddy='''{
  admin off
  auto_https disable_redirects
}
https://HOST {
  tls {
    issuer acme {
      dir https://acme-staging-v02.api.letsencrypt.org/directory
    }
  }
  respond "HTTPS setup in progress" 503
}
http://HOST {
  respond "HTTPS setup in progress" 503
}
http://:80 {
  respond "Not found" 404
}
'''.replace('HOST',host)
    (target/'Caddyfile').write_text(caddy)
    compose={'name':'guten-acme-staging','services':{'caddy':{'image':manifest['images']['caddy'],'platform':'linux/amd64','read_only':True,'restart':'no','security_opt':['no-new-privileges:true'],'ports':['80:80','443:443'],'volumes':[{'type':'bind','source':str(install/'Caddyfile'),'target':'/etc/caddy/Caddyfile','read_only':True,'bind':{'create_host_path':False}},'data:/data','config:/config'],'logging':{'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}}},'volumes':{'data':{},'config':{}}}
    (target/'compose.json').write_text(json.dumps(compose,indent=2)+'\n')
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(prepare(a.release,a.output))
