"""Check isolation, shared read-only assets, and persistence across container replacement."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from urllib.parse import quote
from urllib.request import Request, urlopen
from compose import APPS, DB, ROOT

subprocess.run(APPS + ["exec", "-T", "datalake", "python", "-c",
    "from app.database import parsed_url; assert parsed_url.host == 'postgres' and parsed_url.database == 'guten_compose_test_local' and parsed_url.username == 'guten_app'"], check=True)
artifacts = ROOT / "artifacts" / ("compose_lifecycle_" + time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8])
artifacts.mkdir(parents=True)
report = {"passed": False, "non_root_services": [], "assets_verified": False, "database_persistence": False}

def inspect(service):
    ident = subprocess.check_output(APPS + ["ps", "-q", service], text=True).strip()
    return json.loads(subprocess.check_output(["docker", "inspect", ident], text=True))[0]

def call(method, path, body=None):
    with urlopen(Request("http://127.0.0.1:13001/api/guten"+path, method=method,
                         data=None if body is None else json.dumps(body).encode(),
                         headers={"Content-Type":"application/json"}), timeout=15) as response:
        return json.load(response)

name = "persistence_" + uuid.uuid4().hex
created = False
try:
    for service in ("datalake", "crust", "portal", "sites", "web"):
        uid = subprocess.check_output(APPS + ["exec", "-T", service, "id", "-u"], text=True).strip()
        assert uid != "0", service
        report["non_root_services"].append(service)
        if service != "web":
            assert not inspect(service)["HostConfig"]["PortBindings"], service
            subprocess.run(APPS + ["exec", "-T", service, "sh", "-c", "test ! -f /app/.env"], check=True)
    mounts = [next(m for m in inspect(service)["Mounts"] if m["Destination"] == "/app/public/assets") for service in ("portal","sites")]
    assert mounts[0]["Source"] == mounts[1]["Source"] and all(not m["RW"] for m in mounts)
    assets = Path(mounts[0]["Source"])
    sample = next(assets.rglob("*.png"), None)
    if sample:
        expected = hashlib.sha256(sample.read_bytes()).hexdigest()
        for port in (13000,13001):
            with urlopen(f"http://127.0.0.1:{port}/assets/"+quote(sample.relative_to(assets).as_posix()), timeout=15) as response:
                assert hashlib.sha256(response.read()).hexdigest() == expected
        report["assets_verified"] = True
    else:
        report["assets_note"] = "No PNG available; mount permissions and shared path verified."
    site = call("POST", "/sites", dict(name=name,title="Compose persistence check",url="",logo="",favicon="",color=""))
    created = True
    db_id = subprocess.check_output(DB + ["ps", "-q", "postgres"], text=True).strip()
    subprocess.run(APPS + ["down"], check=True)
    assert subprocess.check_output(DB + ["ps", "-q", "postgres"], text=True).strip() == db_id
    # Explicitly replace only the rehearsal DB container, retaining its external volume.
    subprocess.run(DB + ["up", "-d", "--force-recreate", "--wait"], check=True)
    subprocess.run(APPS + ["up", "-d", "--wait", "--wait-timeout", "180"], check=True)
    restored = call("GET", "/sites/"+name)
    assert restored["id"] == site["id"] and restored["title"] == site["title"]
    report["database_persistence"] = True
    report["passed"] = True
finally:
    if created:
        try: call("DELETE", "/sites/"+name)
        except Exception:
            report["cleanup_failed_site"] = name
            report["passed"] = False
    (artifacts / "results.json").write_text(json.dumps(report, indent=2)+"\n")
    print(f"Lifecycle report: {artifacts}")
if not report["passed"]: raise RuntimeError("Lifecycle verification failed; see report.")
