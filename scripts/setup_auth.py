"""Prepare ignored OAuth files without displaying or replacing existing secrets."""
import base64
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
state = root / ".docker-local"
state.mkdir(mode=0o700, exist_ok=True)
state.chmod(0o700)
files = {
    "oauth2-proxy.cfg": (root / "deploy/oauth2-proxy.cfg.example").read_text(),
    "github_client_secret": "REPLACE_GITHUB_CLIENT_SECRET\n",
    "oauth_cookie_secret": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
}
for name, content in files.items():
    path = state / name
    if not path.exists():
        path.write_text(content)
        # Compose bind secrets need to be readable by a non-root container UID.
        # The enclosing 0700 directory keeps them private on the host.
        path.chmod(0o644)
print("OAuth files ready under .docker-local; existing values preserved.")
print("Set client_id in oauth2-proxy.cfg and put the client secret in github_client_secret.")
