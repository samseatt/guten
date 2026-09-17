"""Local Compose operations; app and database lifecycle commands are separate."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".docker-local"
APPS = ["docker", "compose", "-f", str(ROOT / "deploy/compose.apps.yaml"), "-f", str(ROOT / "deploy/compose.local.yaml")]
DB = ["docker", "compose", "-f", str(ROOT / "deploy/compose.database.yaml")]


def run(args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    action = sys.argv[1]
    if action == "docker-setup":
        if STATE.exists():
            raise RuntimeError(".docker-local already exists; preserving its credentials. Setup is one-time only.")
        STATE.mkdir(mode=0o700)
        for name, value in {
            "postgres_password": secrets.token_urlsafe(32),
            "database_url": "postgresql+asyncpg://guten_app:" + secrets.token_urlsafe(32) + "@postgres:5432/guten_compose_test_local",
        }.items():
            path = STATE / name
            path.write_text(value + "\n")
            path.chmod(0o444)  # Parent is 0700; non-root containers need read access to mounted secrets.
        print("Created ignored local secrets. No database was changed.")
        return
    if not all((STATE / name).is_file() for name in ("postgres_password", "database_url")):
        raise RuntimeError("Run make docker-setup first.")
    if action == "docker-db-up":
        result = subprocess.run(["docker", "volume", "inspect", "guten-local-pgdata", "--format", '{{index .Labels "com.guten.purpose"}}'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip() != "local-rehearsal":
            raise RuntimeError("Existing volume is not labelled for Guten rehearsal; refusing to adopt it.")
        if result.returncode != 0:
            run(["docker", "volume", "create", "--label", "com.guten.purpose=local-rehearsal", "guten-local-pgdata"])
        run(DB + ["up", "-d", "--wait"])
    elif action == "docker-db-stop": run(DB + ["stop"])
    elif action == "docker-build": run(APPS + ["build", "--pull"])
    elif action == "docker-init-test": run(APPS + ["run", "--rm", "--no-deps", "db-init"])
    elif action == "docker-up":
        run(APPS + ["run", "--rm", "--no-deps", "auth", "--config=/run/secrets/oauth_config", "--config-test"])
        run(APPS + ["up", "-d", "--wait", "--wait-timeout", "180"])
        # Bind-mounted configuration changes do not change Compose's service hash.
        # Recreate the gateway services so new credentials and routing are loaded.
        run(APPS + ["up", "-d", "--no-deps", "--force-recreate", "--wait", "--wait-timeout", "180", "auth", "web"])
    elif action == "docker-stop": run(APPS + ["stop"])
    elif action == "docker-down": run(APPS + ["down"])
    elif action == "docker-status":
        run(DB + ["ps"])
        run(APPS + ["ps"])
    elif action == "docker-logs": run(APPS + ["logs", "--tail", "100"])
    elif action == "docker-test-lifecycle": run([sys.executable, "-B", str(ROOT / "scripts/test_compose_lifecycle.py")])
    elif action == "docker-test": run([sys.executable, "-B", str(ROOT / "scripts/test_compose.py")])
    elif action == "docker-config":
        run(DB + ["config", "--quiet"])
        run(APPS + ["config", "--quiet"])
    else: raise RuntimeError("Unknown Docker command")


if __name__ == "__main__":
    try: main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
