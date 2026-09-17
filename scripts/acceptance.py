"""One isolated API/browser run. Requires installed app and browser dependencies."""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.request import urlopen
from dev import repo, stop_children

sys.path.insert(0, str(repo("datalake") / "scripts/database"))
from bootstrap_test_db import create, drop


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    coordination = Path(__file__).resolve().parents[1]
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
    artifacts = coordination / "artifacts" / run_id
    artifacts.mkdir(parents=True)
    database = "guten_acceptance_test_" + uuid.uuid4().hex
    env = dict(os.environ, TEST_DATABASE=database, TEST_ARTIFACTS_DIR=str(artifacts),
               DATABASE_URL=f"postgresql+asyncpg:///{database}", SQL_ECHO="false", LOG_FILE="",
               LOG_LEVEL="INFO", PYTHONDONTWRITEBYTECODE="1", NEXT_TELEMETRY_DISABLED="1")
    children, logs = [], []
    created = False
    result = {"database": database, "passed": False, "database_removed": False}
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupted)
    try:
        print(f"Acceptance reports: {artifacts}", flush=True)
        create(database)
        created = True
        subprocess.run([sys.executable, "-B", str(repo("datalake") / "scripts/run_tests.py")], env=env, check=True)
        ports = set()
        while len(ports) < 4:
            port = free_port()
            if port not in (3000, 3001, 8000, 8005):
                ports.add(port)
        ports = dict(zip(("datalake", "crust", "portal", "sites"), sorted(ports)))
        urls = {name: f"http://127.0.0.1:{port}" for name, port in ports.items()}
        env.update(PORT=str(ports["crust"]), GUTEN_DATALAKE_URL=urls["datalake"],
                   CORS_ORIGINS=urls["portal"]+","+urls["sites"],
                   NEXT_PUBLIC_API_BASE_URL=urls["crust"]+"/api",
                   NEXT_PUBLIC_GUTEN_CRUST_URL=urls["crust"]+"/api/guten",
                   NEXT_PUBLIC_GUTEN_SITES_URL=urls["sites"], GUTEN_ACCEPTANCE_RUN="1",
                   GUTEN_PORTAL_URL=urls["portal"], GUTEN_SITES_URL=urls["sites"],
                   GUTEN_API_URL=urls["crust"]+"/api/guten", GUTEN_ACCEPTANCE_ARTIFACTS_DIR=str(artifacts))
        if sys.platform == "darwin":
            env.setdefault("PLAYWRIGHT_CHANNEL", "chrome")
        with tempfile.TemporaryDirectory(prefix="guten-browser-tests-") as temporary:
            for name in ports:
                directory = repo(name)
                if name == "datalake":
                    args = [sys.executable,"-B","-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(ports[name])]
                elif name == "crust":
                    args = [str(directory / "node_modules/.bin/ts-node"), "src/server.ts"]
                else:
                    source = directory
                    directory = Path(temporary) / name
                    directory.mkdir()
                    # Copy only source/config; no local environments, media archives or shared .next output.
                    for entry in source.iterdir():
                        if entry.name == "src":
                            shutil.copytree(entry, directory / entry.name, ignore=shutil.ignore_patterns(".DS_Store"))
                        elif entry.is_file() and (entry.suffix in (".json", ".js", ".mjs", ".ts") or entry.name == ".eslintrc.json"):
                            shutil.copy2(entry, directory / entry.name)
                    (directory / "node_modules").symlink_to(source / "node_modules", target_is_directory=True)
                    args = ["node", str(source / "node_modules/next/dist/bin/next"), "dev", "--hostname", "127.0.0.1", "-p",str(ports[name])]
                log = (artifacts / (name + ".log")).open("w")
                logs.append(log)
                children.append((name, subprocess.Popen(args, cwd=directory, env=env, stdout=log, stderr=log, start_new_session=True)))
            try:
                for name in ports:
                    endpoint = urls[name] + ("/health/ready" if name in ("datalake", "crust") else "/health")
                    deadline = time.monotonic() + 150
                    while True:
                        if any(child.poll() is not None for _,child in children):
                            raise RuntimeError("A test service exited; see service logs.")
                        try:
                            with urlopen(endpoint, timeout=5) as response:
                                if response.status == 200: break
                        except OSError:
                            if time.monotonic() > deadline:
                                raise RuntimeError(f"{name} did not become ready; see service logs.")
                            time.sleep(.3)
                subprocess.run([str(coordination / "node_modules/.bin/playwright"), "test"], cwd=coordination, env=env, check=True)
                result["passed"] = True
            finally:
                stop_children(children)
                children.clear()
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal.SIG_IGN)
        stop_children(children)
        for log in logs:
            log.close()
        try:
            if created:
                drop(database)
                result["database_removed"] = True
        finally:
            (artifacts / "run.json").write_text(json.dumps(result, indent=2)+"\n")
            print(f"Reports retained: {artifacts}", flush=True)


if __name__ == "__main__":
    main()
