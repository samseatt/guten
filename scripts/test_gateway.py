"""Rehearse the generated HTTPS gateway with .test names and fake GitHub only."""
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
from configure_domains import generate, ROOT


def main():
    token=uuid.uuid4().hex[:10]
    names=['gateway_a_'+token,'gateway_b_'+token]
    artifacts=ROOT/'artifacts'/('gateway_'+time.strftime('%Y%m%dT%H%M%S')+'_'+token)
    artifacts.mkdir(parents=True)
    created=[]
    with tempfile.TemporaryDirectory(prefix='guten-gateway-') as temporary:
        temp=Path(temporary)
        manifest={'portal':'portal.guten.test','sites':[{'host':'alpha.guten.test','site':names[0],'aliases':['www.alpha.guten.test']},{'host':'beta.guten.test','site':names[1]}]}
        generated=generate(manifest,temp/'gateway',test=True)
        config=(ROOT/'deploy/oauth2-proxy.cfg.example').read_text().replace('REPLACE_GITHUB_CLIENT_ID','test-client')
        config+='\nlogin_url = "http://127.0.0.1:13022/login/oauth/authorize"\nredeem_url = "http://fake-github:9000/login/oauth/access_token"\nvalidate_url = "http://fake-github:9000/"\n'
        (temp/'oauth.cfg').write_text(config)
        (temp/'client-secret').write_text('fake-secret')
        (temp/'cookie-secret').write_text(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        overrides={'services':{'sites':{'image':'guten-sites:gateway-test'},'portal':{'image':'guten-portal:gateway-test'},'fake-github':{'image':'python:3.11-slim-bookworm','user':'10001:10001','read_only':True,'command':['python','-B','/fixture.py'],'environment':{'TEST_OAUTH_CALLBACK':'https://portal.guten.test:14443/oauth2/callback'},'ports':['127.0.0.1:13022:9000'],'volumes':[str(ROOT/'tests/auth/fake_github.py')+':/fixture.py:ro']}},'secrets':{'oauth_config':{'file':str(temp/'oauth.cfg')},'github_client_secret':{'file':str(temp/'client-secret')},'oauth_cookie_secret':{'file':str(temp/'cookie-secret')}}}
        (temp/'override.json').write_text(json.dumps(overrides))
        cmd=['docker','compose','-p','guten-gateway-test-'+token,'-f',str(ROOT/'deploy/compose.apps.yaml'),'-f',str(ROOT/'deploy/compose.local.yaml'),'-f',str(generated/'compose.gateway.yaml'),'-f',str(temp/'override.json')]
        def run(args,**kw):return subprocess.run(cmd+args,check=True,**kw)
        def call(method,path,body=None):
            code="""import json,sys
from urllib.request import Request,urlopen
from app.database import parsed_url
assert parsed_url.host=='postgres' and parsed_url.database=='guten_compose_test_local' and parsed_url.username=='guten_app'
method,path,body=sys.argv[1:]
with urlopen(Request('http://127.0.0.1:8005/guten'+path,method=method,data=None if body=='null' else body.encode(),headers={'Content-Type':'application/json'}),timeout=15) as response: print(response.read().decode())
"""
            return json.loads(subprocess.check_output(cmd+['exec','-T','datalake','python','-c',code,method,path,json.dumps(body)],text=True))
        try:
            run(['run','--rm','--no-deps','datalake','python','-c',"from app.database import parsed_url; assert parsed_url.host == 'postgres' and parsed_url.database == 'guten_compose_test_local' and parsed_url.username == 'guten_app'"])
            run(['up','-d','--no-build','--wait','--wait-timeout','180'])
            for name in names:
                call('POST','/sites',dict(name=name,title=name,url='',logo='',favicon='',color=''))
                created.append(name)
                call('POST','/sections',dict(site_name=name,name='first',title='First section',label='First'))
                for page in ('one','two'):
                    call('POST','/pages',dict(site_name=name,section_name='first',name=page,title=page,content='Content for '+name))
                status=call('GET',f'/sites/{name}/publication')
                call('POST','/publish/'+name,dict(expected_fingerprint=status['draft_fingerprint']))
            env=dict(os.environ,GUTEN_GATEWAY_TEST='1',GUTEN_TEST_SITES=json.dumps(names),GUTEN_GATEWAY_ARTIFACTS=str(artifacts))
            if sys.platform=='darwin':env.setdefault('PLAYWRIGHT_CHANNEL','chrome')
            subprocess.run(['node',str(ROOT/'scripts/test_gateway.mjs')],cwd=ROOT,env=env,check=True)
            # Authentication must still fail closed through Caddy when OAuth is unavailable.
            run(['stop','auth'])
            env['GUTEN_TEST_AUTH_OUTAGE']='1'
            subprocess.run(['node',str(ROOT/'scripts/test_gateway.mjs')],cwd=ROOT,env=env,check=True)
        finally:
            try:
                for name in created:
                    status=call('GET',f'/sites/{name}/publication')
                    if status['is_published']:call('DELETE',f'/sites/{name}/publication',dict(expected_fingerprint=status['published_fingerprint']))
                    call('DELETE','/sites/'+name)
            finally:
                with (artifacts/'services.log').open('w') as log:subprocess.run(cmd+['logs','--no-color'],stdout=log,stderr=subprocess.STDOUT)
                run(['down','-v'])
            print('HTTPS gateway reports:',artifacts)


if __name__=='__main__':main()
