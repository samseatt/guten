"""TEST ONLY GitHub OAuth/API fixture. Never part of the normal application stack."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
import html
import json
import secrets
import os

codes = {}
tokens = {}
callback = os.environ.get("TEST_OAUTH_CALLBACK", "http://127.0.0.1:13011/oauth2/callback")
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, status, value, content_type="application/json"):
        data = value.encode() if isinstance(value,str) else json.dumps(value).encode()
        self.send_response(status); self.send_header("Content-Type",content_type); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        url = urlparse(self.path); query=parse_qs(url.query)
        if url.path == "/login/oauth/authorize":
            if query.get("redirect_uri",[""])[0] != callback or query.get("client_id",[""])[0] != "test-client":
                return self.send(400,{"error":"invalid test client"})
            state=query.get("state",[""])[0]
            buttons="".join('<a href="'+html.escape('/approve?'+urlencode(dict(state=state,user=user)),quote=True)+'">'+label+'</a><br>' for user,label in [('samseatt','Approve allowed test account'),('outsider','Approve disallowed test account')])
            return self.send(200,"<h1>Fake GitHub — automated tests only</h1>"+buttons,"text/html")
        if url.path == "/approve":
            user=query.get("user",[""])[0]
            if user not in ("samseatt","outsider"): return self.send(400,{"error":"invalid fixture"})
            code=secrets.token_urlsafe(24);codes[code]=user
            self.send_response(302);self.send_header("Location",callback+'?'+urlencode(dict(code=code,state=query.get('state',[''])[0])));self.end_headers();return
        token=self.headers.get("Authorization", "").split(" ")[-1]
        user=tokens.get(token)
        if not user: return self.send(401,{"error":"bad token"})
        if url.path in ("/user/orgs","/user/teams"): return self.send(200,[])
        if url.path == "/user/emails": return self.send(200,[dict(email=user+'@example.test',primary=True,verified=True)])
        if url.path in ("/", "/user"): return self.send(200,dict(login=user,email=user+'@example.test',id=1 if user=='samseatt' else 2))
        self.send(404,{"error":"unknown endpoint"})
    def do_POST(self):
        data=parse_qs(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
        if self.path != '/login/oauth/access_token': return self.send(404,{})
        user=codes.pop(data.get('code',[''])[0],None)
        if not user: return self.send(400,dict(error='invalid_grant'))
        token=secrets.token_urlsafe(24);tokens[token]=user
        self.send(200,dict(access_token=token,token_type='bearer',scope='user:email read:org'))
ThreadingHTTPServer(('0.0.0.0',9000),Handler).serve_forever()
