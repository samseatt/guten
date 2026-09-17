"""Run stored acceptance scenarios against the local production container stack."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from compose import APPS, DB, ROOT

# Check the RUNNING Datalake connection, not just the host-side example settings.
subprocess.run(APPS + ["exec", "-T", "datalake", "python", "-c",
    "from app.database import parsed_url; assert parsed_url.host == 'postgres' and parsed_url.database == 'guten_compose_test_local' and parsed_url.username == 'guten_app', 'Not the isolated Compose test database'"], check=True)
artifacts = ROOT / "artifacts" / ("compose_" + time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8])
artifacts.mkdir(parents=True)
env = dict(os.environ, GUTEN_ACCEPTANCE_RUN="compose", TEST_DATABASE="guten_compose_test_local",
           GUTEN_PORTAL_URL="http://127.0.0.1:13001", GUTEN_SITES_URL="http://127.0.0.1:13000",
           GUTEN_API_URL="http://127.0.0.1:13001/api/guten", GUTEN_ACCEPTANCE_ARTIFACTS_DIR=str(artifacts))
if sys.platform == "darwin": env.setdefault("PLAYWRIGHT_CHANNEL", "chrome")
try:
    for method, path, expected in [("GET", "/api/guten/sites", 404), ("GET", "/api/guten/notes", 404),
                                    ("POST", "/api/guten/publish/test", 404), ("POST", "/api/guten/published/sites/test/page", 403)]:
        try:
            with urlopen(Request("http://127.0.0.1:13000"+path, method=method), timeout=10) as response: code=response.status
        except HTTPError as error: code=error.code
        assert code == expected, (method,path,code)
    subprocess.run([str(ROOT / "node_modules/.bin/playwright"), "test"], cwd=ROOT, env=env, check=True)
    web_before = subprocess.check_output(APPS + ["ps", "-q", "web"], text=True).strip()
    subprocess.run(APPS + ["up", "-d", "--no-deps", "--force-recreate", "--wait", "crust"], check=True)
    deadline = time.monotonic() + 30
    while True:
        try:
            with urlopen("http://127.0.0.1:13001/api/guten/sites", timeout=5) as response:
                assert response.status == 200
            break
        except OSError:
            if time.monotonic() > deadline: raise
            time.sleep(1)
    assert subprocess.check_output(APPS + ["ps", "-q", "web"], text=True).strip() == web_before
    print("Production-container workflows, public API restrictions and upstream replacement passed.")
finally:
    with (artifacts / "services.log").open("w") as stream:
        subprocess.run(APPS + ["logs", "--no-color"], stdout=stream, stderr=subprocess.STDOUT)
    print(f"Reports: {artifacts}")
