"""Exercise the real OAuth proxy with a fake GitHub provider on separate loopback ports."""
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from compose import ROOT

artifacts=ROOT / "artifacts" / ("auth_"+time.strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8])
artifacts.mkdir(parents=True)
with tempfile.TemporaryDirectory(prefix="guten-auth-test-") as temp:
    temp=Path(temp)
    config=(ROOT/'deploy/oauth2-proxy.cfg.example').read_text().replace('REPLACE_GITHUB_CLIENT_ID','test-client')
    config+='\nlogin_url = "http://127.0.0.1:13012/login/oauth/authorize"\nredeem_url = "http://fake-github:9000/login/oauth/access_token"\nvalidate_url = "http://fake-github:9000/"\n'
    (temp/'oauth.cfg').write_text(config)
    (temp/'client-secret').write_text('fake-secret')
    (temp/'cookie-secret').write_text(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    nginx=(ROOT/'deploy/nginx.conf').read_text().replace(':13001',':13011')
    (temp/'nginx.conf').write_text(nginx)
    # Override only the proxy/provider settings; production app images and database permissions remain real.
    overlay={"services":{
        "auth":{"environment":{"OAUTH2_PROXY_REDIRECT_URL":"http://127.0.0.1:13011/oauth2/callback","OAUTH2_PROXY_WHITELIST_DOMAINS":"127.0.0.1:13011"}},
        "web":{"volumes":[{"type":"bind","source":str(temp/'nginx.conf'),"target":"/etc/nginx/nginx.conf","read_only":True}]},
        "fake-github":{"image":"python:3.11-slim-bookworm","user":"10001:10001","read_only":True,
            "command":["python","-B","/fixture.py"],"ports":["127.0.0.1:13012:9000"],
            "volumes":[str(ROOT/'tests/auth/fake_github.py')+":/fixture.py:ro"]}},
        "secrets":{"oauth_config":{"file":str(temp/'oauth.cfg')},"github_client_secret":{"file":str(temp/'client-secret')},"oauth_cookie_secret":{"file":str(temp/'cookie-secret')}}}
    (temp/'override.json').write_text(json.dumps(overlay))
    # !override is supported by the installed Compose v2.31 and prevents retaining normal host ports.
    (temp/'ports.yaml').write_text('services:\n  web:\n    ports: !override ["127.0.0.1:13010:8080", "127.0.0.1:13011:8081"]\n')
    command=['docker','compose','-p','guten-auth-test','-f',str(ROOT/'deploy/compose.apps.yaml'),'-f',str(ROOT/'deploy/compose.local.yaml'),'-f',str(temp/'override.json'),'-f',str(temp/'ports.yaml')]
    state=temp/'session.json'
    env=dict(os.environ,GUTEN_ACCEPTANCE_RUN='compose',TEST_DATABASE='guten_compose_test_local',GUTEN_AUTH_TEST='1',
        GUTEN_PORTAL_URL='http://127.0.0.1:13011',GUTEN_SITES_URL='http://127.0.0.1:13010',GUTEN_API_URL='http://127.0.0.1:13011/api/guten',
        GUTEN_ACCEPTANCE_ARTIFACTS_DIR=str(artifacts),GUTEN_AUTH_STATE=str(state),GUTEN_AUTH_RESULTS=str(artifacts/'auth-results.json'))
    if sys.platform=='darwin': env.setdefault('PLAYWRIGHT_CHANNEL','chrome')
    try:
        subprocess.run(command+['up','-d','--wait','--wait-timeout','180'],check=True)
        subprocess.run(command+['exec','-T','datalake','python','-c',"from app.database import parsed_url; assert parsed_url.host == 'postgres' and parsed_url.database == 'guten_compose_test_local' and parsed_url.username == 'guten_app'"],check=True)
        subprocess.run(['node',str(ROOT/'scripts/auth_session.mjs')],cwd=ROOT,env=env,check=True)
        for method,path,expected in [('GET','/api/guten/sites',404),('POST','/api/guten/publish/test',404),('POST','/api/guten/published/sites/test/page',403)]:
            try:
                with urlopen(Request('http://127.0.0.1:13010'+path,method=method),timeout=10) as response: code=response.status
            except HTTPError as error: code=error.code
            assert code==expected,(method,path,code)
        subprocess.run([str(ROOT/'node_modules/.bin/playwright'),'test'],cwd=ROOT,env=env,check=True)
        # Keep the existing Docker DNS/replacement regression check through the auth gate.
        web_before=subprocess.check_output(command+['ps','-q','web'],text=True).strip()
        subprocess.run(command+['up','-d','--no-deps','--force-recreate','--wait','crust'],check=True)
        cookie='; '.join(c['name']+'='+c['value'] for c in json.loads(state.read_text())['cookies'])
        deadline=time.monotonic()+30
        while True:
            try:
                with urlopen(Request('http://127.0.0.1:13011/api/guten/sites',headers={'Cookie':cookie}),timeout=5) as response: assert response.status==200
                break
            except OSError:
                if time.monotonic()>deadline: raise
                time.sleep(1)
        assert subprocess.check_output(command+['ps','-q','web'],text=True).strip()==web_before
        subprocess.run(command+['stop','auth'],check=True)
        for protected_path in ('/dashboard','/api/guten/sites'):
            try:
                urlopen('http://127.0.0.1:13011'+protected_path,timeout=10)
                raise AssertionError('Authentication outage must not expose Portal')
            except HTTPError as error: assert error.code in (502,503,504)
        with urlopen('http://127.0.0.1:13010/health',timeout=10) as response: assert response.status==200
        (artifacts/'proxy-results.json').write_text(json.dumps(dict(passed=True,public_restrictions=True,upstream_replacement=True,auth_outage_fails_closed=True)))
        print('Authentication, browser workflows, public API restrictions and fail-closed outage checks passed.')
    finally:
        with (artifacts/'services.log').open('w') as stream: subprocess.run(command+['logs','--no-color'],stdout=stream,stderr=subprocess.STDOUT)
        subprocess.run(command+['down'],check=True)
        print(f'Reports retained: {artifacts}')
