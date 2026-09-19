#!/usr/bin/env python3
"""Inventory referenced /assets media and create a checksummed bundle; never delete sources."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import os
import tempfile
import io
import subprocess
import tarfile
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
TOKEN=re.compile(r'''(?:https?://|//)[^\s<>"'`]+|/?assets/[^\s<>"'`]+''')


def local_path(value,hosts):
    value=html.unescape(value).strip()
    parsed=urlsplit(value)
    if parsed.scheme and parsed.scheme not in ('http','https'):return None
    if parsed.netloc and parsed.hostname not in hosts:return None
    path=unquote(parsed.path)
    if path.startswith('assets/'):path='/'+path
    if not path.startswith('/assets/'):return None
    relative=path[len('/assets/'):]
    if '\\' in relative or any(p in ('','..','.') for p in relative.split('/')) or '\x00' in relative:
        raise ValueError('Unsafe asset path: '+path)
    return relative


def references(text,hosts,standalone=False):
    # URL fields preserve literal spaces/parentheses; prose uses Markdown/HTML/CSS
    # token boundaries. Percent-encoded filenames work in either context.
    if standalone:
        path=local_path(text,hosts)
        return {path} if path else set()
    found=set()
    for match in TOKEN.finditer(text):
        token=match.group().rstrip('.,;]}')
        # Keep balanced parentheses belonging to filenames, remove Markdown's close.
        while token.endswith(')') and token.count(')') > token.count('('):
            token=token[:-1]
        path=local_path(token,hosts)
        if path:found.add(path)
    return found


def snapshot():
    def query(sql):
        return subprocess.check_output(['psql','-X','-q','-A','-t','-w','-v','ON_ERROR_STOP=1','-d','guten_datalake','-c','BEGIN READ ONLY','-c',sql,'-c','COMMIT'],text=True)
    names=json.loads(query("SELECT json_agg(t) FROM (SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('draft','published') AND tablename <> 'users' ORDER BY 1,2) t"))
    parts=[]
    for name in names:
        schema,table=name['schemaname'],name['tablename']
        if not re.fullmatch('[a-z_]+',schema+table):raise ValueError('Unexpected table name')
        parts.append(f"SELECT '{schema}' AS schema, '{table}' AS table, to_jsonb(t) AS record FROM {schema}.{table} t")
    return json.loads(query('SELECT json_agg(t) FROM ('+' UNION ALL '.join(parts)+') t'))


def inventory(records,assets):
    assets=assets.resolve()
    sites=[r for r in records if r['table']=='sites']
    hosts=set()
    domains=[]
    for row in sites:
        record=row['record'];url=record.get('url','') or ''
        host=urlsplit(url if '://' in url else '//'+url).hostname
        if host:hosts.add(host);hosts.add('www.'+host)
        if row['schema']=='published':domains.append({'site':record['name'],'host':host,'source_url':url})
    refs={'default.png':['application fallback']};external=set();invalid=[];unresolved=[]
    def walk(value,location,field=None):
        if isinstance(value,dict):
            for key,item in value.items():walk(item,location+'.'+key,key)
        elif isinstance(value,list):
            for i,item in enumerate(value):walk(item,location+f'[{i}]')
        elif isinstance(value,str):
            try:
                for name in references(value,hosts,field in ('primary_image','logo','favicon')):refs.setdefault(name,[]).append(location)
            except ValueError as exc:invalid.append({'location':location,'error':str(exc)})
            if field in ('primary_image','logo','favicon') and value and not value.startswith(('/', 'assets/', 'http://', 'https://')):
                unresolved.append({'location':location,'value':value})
            for url in re.findall(r'https?://[^\s<>"\']+',value):
                if '/assets/' in url and urlsplit(url).hostname not in hosts:external.add(url)
    for row in records:
        record=row['record'];walk(record,f"{row['schema']}.{row['table']}[{record.get('id','?')}]")
    files=[];missing=[]
    for name,locations in sorted(refs.items()):
        path=assets/name
        if path.is_symlink() or not path.resolve().is_relative_to(assets):
            invalid.append({'path':name,'error':'symlink/escape'});continue
        if not path.is_file():missing.append({'path':name,'locations':sorted(set(locations))});continue
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        files.append({'path':name,'bytes':path.stat().st_size,'sha256':digest,'locations':sorted(set(locations))})
    all_files=[p for p in assets.rglob('*') if p.is_file() and not p.is_symlink() and p.name!='.DS_Store']
    return {'format':1,'files':files,'missing':missing,'invalid':invalid,'unresolved_image_fields':unresolved,'external_asset_urls':sorted(external),'domains':sorted(domains,key=lambda r:r['site']),'total_source_files':len(all_files),'total_source_bytes':sum(p.stat().st_size for p in all_files),'selected_bytes':sum(f['bytes'] for f in files)}


def bundle(report,assets,target,allow_missing=()):
    missing={entry['path'] for entry in report['missing']}
    if report['invalid'] or missing != set(allow_missing):
        raise ValueError('Unsafe references or missing paths not explicitly acknowledged')
    assets=assets.resolve()
    if target.exists():raise ValueError('Refusing to overwrite bundle')
    target.parent.mkdir(parents=True,exist_ok=True)
    # Write privately, expose the complete archive only after every checksum passes.
    with tempfile.TemporaryDirectory(prefix='.media-',dir=target.parent) as temporary:
        pending=Path(temporary)/'bundle.tar'
        with tarfile.open(pending,'x') as archive:
            for entry in report['files']:
                name=entry['path']
                if local_path('/assets/'+name,set()) != name:
                    raise ValueError('Unsafe inventory path')
                path=assets/name
                if path.is_symlink() or not path.resolve().is_relative_to(assets):
                    raise ValueError('Source symlink/escape during packaging')
                with path.open('rb') as stream:
                    if (os.fstat(stream.fileno()).st_size != entry['bytes'] or
                        hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']):
                        raise ValueError('Source changed during packaging')
                    stream.seek(0)
                    info=tarfile.TarInfo('assets/'+name);info.size=entry['bytes'];info.mode=0o644
                    archive.addfile(info,stream)
            data=(json.dumps(report,indent=2)+'\n').encode()
            info=tarfile.TarInfo('media-manifest.json');info.size=len(data);info.mode=0o644
            archive.addfile(info,io.BytesIO(data))
        # Verify archived bytes, including changes made while the tar was written.
        with tarfile.open(pending) as archive:
            for entry in report['files']:
                with archive.extractfile('assets/'+entry['path']) as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:
                        raise ValueError('Source changed while writing archive')
        os.link(pending,target)  # exclusive, atomic publication on the same filesystem
    with target.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',type=Path,default=ROOT.parent/'guten-sites/public/assets')
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--bundle',type=Path)
    p.add_argument('--allow-missing',action='append',default=[],help='Exact missing asset path to acknowledge; repeat as needed.')
    a=p.parse_args()
    if a.report.exists():p.error('Report already exists')
    report=inventory(snapshot(),a.assets)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({k:report[k] for k in ['total_source_files','total_source_bytes','selected_bytes']}))
    print(f"Selected {len(report['files'])} files; missing {len(report['missing'])}; unsafe {len(report['invalid'])}")
    if a.bundle:print('Bundle SHA256:',bundle(report,a.assets,a.bundle,a.allow_missing))
