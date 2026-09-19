#!/usr/bin/env python3
"""Prepare a loopback-only public-site rehearsal using existing cloud backends."""
import argparse
import copy
import json
from pathlib import Path
from configure_domains import generate
from deploy_release import verify


def prepare(release,domains,target):
    verify(release)
    if target.exists():raise ValueError('Output exists')
    generate(domains,target/'gateway')
    nginx=target/'gateway/nginx.conf'
    nginx.write_text(nginx.read_text().replace('set $frontend_backend sites:3000;','set $frontend_backend preview_sites:3000;'))
    config=json.loads((release/'compose.json').read_text())
    sites=copy.deepcopy(config['services']['sites']);sites.pop('depends_on',None)
    sites['environment']['GUTEN_DOMAIN_MAP']=json.dumps({entry['host']:{'site':entry['site'],'origin':'https://'+entry['host']} for entry in domains['sites']})
    web=copy.deepcopy(config['services']['web']);web.pop('depends_on',None)
    web['depends_on']={'preview_sites':{'condition':'service_healthy'}}
    web['ports']=['127.0.0.1:18082:8080']
    web['volumes']=[{'type':'bind','source':'/opt/guten/public-preview/gateway/nginx.conf','target':'/etc/nginx/nginx.conf','read_only':True,'bind':{'create_host_path':False}}]
    # This check uses the candidate Sites image, not production Portal's health.
    web['healthcheck']['test']=['CMD','wget','-q','-O','/dev/null','http://preview_sites:3000/health']
    compose={'name':'guten-public-preview','services':{'preview_sites':sites,'preview_web':web},'networks':{'default':{'external':True,'name':'guten-prod'}}}
    (target/'compose.json').write_text(json.dumps(compose,indent=2)+'\n')
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',type=Path,required=True)
    p.add_argument('--domains',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(prepare(a.release,json.loads(a.domains.read_text()),a.output))
