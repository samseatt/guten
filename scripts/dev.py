#!/usr/bin/env python3
"""Small, dependency-free local command interface for the Guten repositories."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(os.environ.get("GUTEN_ROOT") or Path(__file__).resolve().parents[2])
PORTS = {"datalake": 8005, "crust": 8000, "portal": 3001, "sites": 3000}
HELP = """Guten local operations (run make from this repository)
  make status                       Check listeners; does not claim API health
  make up                           Run all four services; Ctrl+C stops this run
  make run SERVICE=portal           Run one service; Ctrl+C stops this run
  make check [SERVICE=crust]        Check Python syntax / TypeScript, no emitted files
  make build [SERVICE=portal]       Production build; refuses running selected services
  make migrate DATABASE=guten_*_test_*  Apply database migrations (master needs ALLOW_MASTER=1)
  make test TEST_DATABASE=guten_*_test_* Run API integration tests against a rehearsal database
  make backup [ARCHIVE_ROOT=/path]  Archive guten_datalake schema and content
  make restore ARCHIVE=/path TARGET=guten_restore_name

Services: datalake, crust, portal, sites. Native PostgreSQL must already be running.
Settings: local.mk (see local.mk.example). No installs, commits, pushes, or deployments.
"""


def repo(service):
    path = ROOT / ("guten-" + service)
    if not path.is_dir():
        raise RuntimeError(f"Missing repository: {path}")
    return path


def listening(port):
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except ConnectionRefusedError:
        return False
    except OSError as exc:
        raise RuntimeError(f"Cannot check local port {port}: {exc}") from exc


def selected():
    service = os.environ.get("SERVICE", "")
    if service and service not in PORTS:
        raise RuntimeError(f"Unknown SERVICE: {service}")
    return [service] if service else list(PORTS)


def python_command():
    return os.environ.get("DATALAKE_PYTHON") or sys.executable


def command(service):
    directory = repo(service)
    if service == "datalake":
        return [python_command(), "-B", "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", str(PORTS[service]), "--reload"]
    if service == "crust":
        return [str(directory / "node_modules/.bin/ts-node"), "src/server.ts"]
    return ["npm", "run", "dev", "--", "-p", str(PORTS[service])]


def preflight(services):
    for name in services:
        repo(name)
        if listening(PORTS[name]):
            raise RuntimeError(f"Port {PORTS[name]} ({name}) is occupied. Stop the existing service in its own terminal first.")
    if "datalake" in services:
        if not listening(5432):
            raise RuntimeError("PostgreSQL is not listening on localhost:5432. Start your existing PostgreSQL installation.")
        subprocess.run([python_command(), "-B", "-c", "import uvicorn, fastapi, sqlalchemy, asyncpg"], check=True)
    for name in services:
        if name != "datalake":
            executable = "ts-node" if name == "crust" else "next"
            if not (repo(name) / "node_modules/.bin" / executable).exists():
                raise RuntimeError(f"Missing {name} dependencies. Install them in {repo(name)} first.")


def stop_children(children):
    # These process groups were created by this invocation, not discovered by port.
    for name, child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 8
    for name, child in children:
        try:
            child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # A parent may exit before its descendants; terminate any remaining group.
    for name, child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def supervise(jobs):
    children = []
    old_handlers = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, interrupted)
        for name, directory, args, environment in jobs:
            print(f"Starting {name} in {directory}", flush=True)
            child = subprocess.Popen(args, cwd=directory, env=environment, start_new_session=True)
            children.append((name, child))
        while True:
            for name, child in children:
                if child.poll() is not None:
                    raise RuntimeError(f"{name} exited with status {child.returncode}; stopping this run.")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping services started by this run.", flush=True)
    finally:
        # Let cleanup finish even if Ctrl+C is pressed a second time.
        for sig in old_handlers:
            signal.signal(sig, signal.SIG_IGN)
        stop_children(children)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


def run_services(services):
    preflight(services)
    jobs = []
    for name in services:
        environment = dict(os.environ)
        if name == "crust":
            environment["PORT"] = str(PORTS[name])
        jobs.append((name, repo(name), command(name), environment))
    supervise(jobs)


def check_or_build(action, services):
    if action == "build":
        occupied = [name for name in services if listening(PORTS[name])]
        if occupied:
            raise RuntimeError("Stop these services before building (build output is shared): " + ", ".join(occupied))
    failed = []
    for name in services:
        directory = repo(name)
        print(f"{action}: {name}", flush=True)
        if name == "datalake":
            # Python is interpreted. Syntax-check without importing the application,
            # opening DB connections, or creating bytecode files.
            for folder in (directory / "app", directory / "utils"):
                for path in folder.rglob("*.py"):
                    compile(path.read_bytes(), str(path), "exec")
            continue
        if action == "check":
            args = [str(directory / "node_modules/.bin/tsc"), "--noEmit", "--incremental", "false"]
        elif name == "crust":
            args = [str(directory / "node_modules/.bin/tsc")]
        else:
            args = ["npm", "run", "build"]
        if subprocess.run(args, cwd=directory).returncode:
            failed.append(name)
    if failed:
        raise RuntimeError(f"{action} failed: " + ", ".join(failed))


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else "help"
    if action == "help":
        print(HELP)
    elif action == "status":
        for name, port in {"postgres": 5432, **PORTS}.items():
            print(f"{name:10} localhost:{port:<5} {'LISTENING' if listening(port) else 'STOPPED'}")
    elif action in ("up", "run"):
        services = selected()
        if action == "run" and len(services) != 1:
            raise RuntimeError("Specify exactly one SERVICE for make run.")
        run_services(services)
    elif action in ("check", "build"):
        check_or_build(action, selected())
    elif action == "migrate":
        database = os.environ.get("DATABASE", "")
        if not database:
            raise RuntimeError("Specify DATABASE explicitly. Rehearse before migrating the master.")
        args = [python_command(), "-B", str(repo("datalake") / "scripts/database/migrate.py"), "--database", database]
        if os.environ.get("ALLOW_MASTER") == "1":
            args.append("--allow-master")
        subprocess.run(args, check=True)
    elif action == "test":
        subprocess.run([python_command(), "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=repo("datalake"), check=True)
    elif action == "backup":
        args = ["bash", str(repo("datalake") / "scripts/database/backup.sh")]
        if os.environ.get("ARCHIVE_ROOT"):
            args.append(os.environ["ARCHIVE_ROOT"])
        subprocess.run(args, check=True)
    elif action == "restore":
        if not os.environ.get("ARCHIVE") or not os.environ.get("TARGET"):
            raise RuntimeError("Specify ARCHIVE and TARGET; see make help.")
        subprocess.run(["bash", str(repo("datalake") / "scripts/database/restore.sh"),
                        os.environ["ARCHIVE"], os.environ["TARGET"]], check=True)
    else:
        raise RuntimeError(f"Unknown action: {action}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError, SyntaxError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
