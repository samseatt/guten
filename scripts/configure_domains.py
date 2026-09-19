"""Generate a Caddy/Nginx/Compose gateway from an explicit publication allowlist."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def generate(manifest, target, test=False):
    target = Path(target).resolve()
    # Restrict interpolated values to DNS labels/slugs, never raw server directives.
    def hostname(value):
        if not isinstance(value, str) or len(value) > 253 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value):
            raise ValueError("Invalid lowercase hostname")
        if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in value.split('.')) or '.' not in value:
            raise ValueError("Expected a fully qualified hostname")
        return value
    portal = hostname(manifest['portal'])
    occupied, domains, aliases = {portal}, {}, {}
    for item in manifest['sites']:
        host = hostname(item['host'])
        site = item['site']
        if not isinstance(site, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', site):
            raise ValueError('Invalid site slug')
        if any(entry['site'] == site for entry in domains.values()): raise ValueError('Use aliases for multiple hostnames of the same site')
        if host in occupied: raise ValueError('Duplicate hostname: '+host)
        occupied.add(host)
        domains[host] = {'site': site, 'origin': 'https://'+host+(':14443' if test else '')}
        for alias in item.get('aliases', []):
            alias = hostname(alias)
            if alias in occupied: raise ValueError('Duplicate hostname: '+alias)
            occupied.add(alias)
            aliases[alias] = host
    if not domains and manifest.get('portal_only') is not True:
        raise ValueError('At least one publication is required unless portal_only is explicitly true')
    if domains and manifest.get('portal_only'):
        raise ValueError('portal_only cannot include publication domains')
    if test and any(not h.endswith('.test') for h in occupied):
        raise ValueError('Local TLS rehearsal requires .test names only')
    if not test and any(h.endswith(('.test', '.localhost', '.invalid')) for h in occupied):
        raise ValueError('Test domains are not production names')
    if target.exists(): raise ValueError('Output directory already exists; generate a new release directory')
    target.mkdir(parents=True, mode=0o700)
    suffix = ':14443' if test else ''
    tls = '  tls internal\n' if test else ''
    caddy = '{\n  admin off\n  auto_https disable_redirects\n'+('  skip_install_trust\n  http_port 18080\n  https_port 14443\n' if test else '')+'}\n'
    for host, upstream in [(portal,'web:8081')] + [(host,'web:8080') for host in domains]:
        caddy += f'\nhttps://{host}{suffix} {{\n{tls}  reverse_proxy {upstream}\n}}\n'
    for alias, host in aliases.items():
        caddy += f'\nhttps://{alias}{suffix} {{\n{tls}  redir https://{host}{suffix}{{uri}} permanent\n}}\n'
    # Explicit redirect targets also work on nonstandard loopback rehearsal ports.
    for host in sorted(occupied):
        canonical = aliases.get(host, host)
        http_suffix = ':18080' if test else ''
        caddy += f'\nhttp://{host}{http_suffix} {{\n  redir https://{canonical}{suffix}{{uri}} permanent\n}}\n'
    caddy += f'\nhttp://:{18080 if test else 80} {{\n  respond "Not found" 404\n}}\n'
    (target/'Caddyfile').write_text(caddy)
    nginx = (ROOT/'deploy/nginx.conf').read_text()
    # Dedicated cloud config: HTTP is internal, the only caller is the Caddy service.
    start=nginx.index('  map $http_origin')
    end=nginx.index('  map "$request_method',start)
    nginx=nginx[:start]+f'  map $http_origin $portal_origin_ok {{\n    default 0;\n    "https://{portal}{suffix}" 1;\n  }}\n'+nginx[end:]
    nginx=nginx.replace('  client_body_temp_path', '  map $host $publication_site {\n    default "";\n'+''.join(f'    {host} "{entry["site"]}";\n' for host,entry in domains.items())+'  }\n  client_body_temp_path',1)
    nginx=nginx.replace('X-Forwarded-Proto $scheme','X-Forwarded-Proto https')
    nginx=nginx.replace('    listen 8080;', '    listen 8080;\n    if ($publication_site = "") { return 404; }')
    nginx=nginx.replace('    location /api/guten/published/ {', '    location ~ ^/api/guten/published/sites/([^/]+)/(landing|page)$ {\n      set $requested_site $1;\n      if ($requested_site != $publication_site) { return 404; }')
    nginx=nginx.replace('    listen 8081;', f'    listen 8081;\n    if ($host != "{portal}") {{ return 404; }}')
    # Hide Next.js internal middleware control headers from external callers.
    nginx=nginx.replace('  proxy_set_header Host', '  proxy_set_header X-Middleware-Subrequest "";\n  proxy_set_header Host',1)
    (target/'nginx.conf').write_text(nginx)
    # Compose !override prevents retaining loopback rehearsal ports/old gateway mounts.
    overlay='''services:
  crust:
    environment:
      CORS_ORIGINS: ORIGINS_VALUE
  sites:
    environment:
      GUTEN_DOMAIN_MAP: MAP_VALUE
  portal:
    environment:
      GUTEN_PUBLIC_DOMAIN_MAP: PUBLIC_MAP_VALUE
  auth:
    environment:
      OAUTH2_PROXY_REDIRECT_URL: REDIRECT_VALUE
      OAUTH2_PROXY_WHITELIST_DOMAINS: HOST_VALUE
      OAUTH2_PROXY_COOKIE_SECURE: "true"
  web:
    ports: !override []
    volumes: !override
      - type: bind
        source: NGINX_VALUE
        target: /etc/nginx/nginx.conf
        read_only: true
    healthcheck:
      test: [CMD, wget, -q, -O, /dev/null, "http://127.0.0.1:8082/health"]
  caddy:
    image: caddy:2.11.2-alpine@sha256:834468128c7696cec0ceea6172f7d692daf645ae51983ca76e39da54a97c570d
    restart: unless-stopped
    read_only: true
    security_opt: ["no-new-privileges:true"]
    ports: PORTS_VALUE
    volumes:
      - type: bind
        source: CADDY_VALUE
        target: /etc/caddy/Caddyfile
        read_only: true
      - caddy_data:/data
      - caddy_config:/config
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}
    depends_on:
      web: {condition: service_healthy}
volumes:
  caddy_data:
  caddy_config:
'''
    values={'ORIGINS_VALUE':json.dumps(','.join(['https://'+portal+suffix]+[entry['origin'] for entry in domains.values()])), 'PUBLIC_MAP_VALUE':json.dumps(json.dumps({entry['site']:entry['origin'] for entry in domains.values()})), 'MAP_VALUE':json.dumps(json.dumps(domains)), 'REDIRECT_VALUE':json.dumps('https://'+portal+suffix+'/oauth2/callback'), 'HOST_VALUE':json.dumps(portal+suffix), 'NGINX_VALUE':json.dumps(str(target/'nginx.conf')), 'CADDY_VALUE':json.dumps(str(target/'Caddyfile')), 'PORTS_VALUE':json.dumps(['127.0.0.1:18080:18080','127.0.0.1:14443:14443'] if test else ['80:80','443:443'])}
    for key,value in values.items(): overlay=overlay.replace(key,value)
    (target/'compose.gateway.yaml').write_text(overlay)
    (target/'domains.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--test',action='store_true',help='Local-only internal CA, .test domains and loopback ports')
    args=parser.parse_args()
    print(generate(json.loads(args.manifest.read_text()),args.output,args.test))
