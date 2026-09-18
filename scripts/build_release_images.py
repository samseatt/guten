#!/usr/bin/env python3
"""Build app images from committed Git archives; registry publication requires --push."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
from package_release import ROOT, APPS, sources


def run(args, **kwargs):
    return subprocess.run(args,check=True,**kwargs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry',required=True,help='Registry namespace, e.g. ghcr.io/samseatt')
    p.add_argument('--output',type=Path,required=True,help='New image build record; never overwritten.')
    p.add_argument('--push',action='store_true',help='Explicitly publish the four built images to the registry.')
    a=p.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9./_-]+',a.registry): p.error('Invalid registry namespace.')
    if a.output.exists(): p.error('Output already exists.')
    revisions=sources(ROOT.parent)
    record={'source_commits':revisions,'platform':'linux/amd64','images':{}}
    # Build all images successfully before publishing any of them.
    with tempfile.TemporaryDirectory(prefix='guten-build-') as directory:
        for service in APPS:
            repo='guten-'+service
            revision=revisions[repo]
            context=Path(directory)/repo
            context.mkdir()
            archive=Path(directory)/(repo+'.tar')
            run(['git','-C',str(ROOT.parent/repo),'archive','--format=tar','--output',str(archive),revision])
            run(['tar','-xf',str(archive),'-C',str(context)])
            tag=a.registry.rstrip('/')+'/'+repo+':'+revision
            args=['docker','build','--pull','--platform','linux/amd64','--label','org.opencontainers.image.revision='+revision,'-t',tag]
            if service in ('portal','sites'):
                args+=['--build-arg','NEXT_PUBLIC_API_BASE_URL=/api','--build-arg','NEXT_PUBLIC_GUTEN_SITES_URL=https://guten.ink']
            if service=='portal': args+=['--build-arg','NEXT_PUBLIC_AUTH_ENABLED=true']
            run([*args,str(context)])
            record['images'][service]={'tag':tag,'source_commit':revision}
    if a.push:
        for service,entry in record['images'].items():
            run(['docker','push',entry['tag']])
            inspect=run(['docker','image','inspect',entry['tag']],capture_output=True,text=True)
            digests=json.loads(inspect.stdout)[0].get('RepoDigests',[])
            repository=entry['tag'].rsplit(':',1)[0]
            matching=[v for v in digests if v.startswith(repository+'@sha256:')]
            if len(matching)!=1: raise RuntimeError('Could not identify published digest for '+service)
            entry['digest']=matching[0]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as stream: json.dump(record,stream,indent=2); stream.write('\n')
    print('Build record:',a.output)


if __name__=='__main__': main()
