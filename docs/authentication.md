# Portal authentication

Docker Portal uses OAuth2 Proxy 7.15.4 (image digest pinned) and GitHub sign-in. The approved GitHub usernames are configured in `github_users`, initially only `samseatt`. Every approved editor has the same site-management permissions. Guten stores no account passwords. The public Sites listener remains anonymous and exposes only published read APIs.

## Local setup

Run `make auth-setup` once. It creates missing files in ignored `.docker-local/`, preserving existing files. Create a [GitHub OAuth App](https://github.com/settings/applications/new) named **Guten Portal — Local** with homepage `http://localhost:13001` and callback `http://localhost:13001/oauth2/callback`.

1. Replace `REPLACE_GITHUB_CLIENT_ID` in `.docker-local/oauth2-proxy.cfg` with the client ID.
2. Put only the client secret in `.docker-local/github_client_secret`. Keep it out of chat, Git, screenshots and build arguments.
3. Run `make docker-build` followed by `make docker-up`.
4. Visit `http://localhost:13001/` and sign in. Use **localhost**, matching the registered callback.

The provider requests `user:email read:org`; it does not request repository access. The provider uses organization/team lookups even with a username allowlist. The email wildcard does not bypass that username allowlist.

The generated cookie key must remain private. Its file contains a base64-encoded 32-byte key with no trailing newline. `.docker-local/` is mode 0700; mounted secret files are readable by their designated non-root containers. Compose secrets here are local file mounts, not encrypted storage. Copy these configuration files securely if needed, separately from source archives.

## Sessions and access changes

Cookies are HttpOnly, host-only and SameSite=Lax, with a one-hour lifetime and a 15-minute refresh interval. Production defaults require Secure cookies; only the loopback rehearsal overlay disables Secure for HTTP. **Sign out** clears the Guten session; it does not sign out of GitHub itself. A still-valid copied cookie remains usable until expiration, so protect browser sessions.

To add editors, change `github_users` in the local configuration and restart `auth`:

```bash
docker compose -f deploy/compose.apps.yaml -f deploy/compose.local.yaml restart auth
```

Allowlist changes do not immediately invalidate existing cookies. For urgent revocation, remove the username, replace the cookie key with a fresh base64-encoded 32-byte key (no newline), and restart `auth`. This signs out all editors. Restart also reloads client-secret changes.

All browser access to Docker Portal, including `/api/`, passes through the auth proxy. Unauthenticated API requests return 401; pages show sign-in. A non-allowlisted GitHub account is denied; this provider version displays a generic error page for that denial. Nginx rejects editing requests without an allowed Origin. An auth outage fails closed. The application ports and the internal authenticated upstream are not published. Do not publish them to bypass login. Native `make up` is deliberately unauthenticated development on localhost; it is not the deployment entry point.

## Tests and deployment boundary

`make docker-test` starts a separate temporary Compose project on ports 13010–13012 and drives the real auth proxy against a local fake GitHub provider. It uses fake credentials, the rehearsal database and the production application images. It checks denied/approved accounts, spoofed headers, forged callbacks/cookies, CSRF, logout, authenticated editing/publishing workflows, public API restrictions and an auth outage. Temporary login cookies are deleted afterward. Reports remain in ignored `artifacts/auth_*`. The fake provider is not included in normal Compose files. Real GitHub consent/login still requires a manual smoke test.

For Lightsail, create a separate OAuth App with homepage `https://portal.guten.ink` and callback `https://portal.guten.ink/oauth2/callback`. Keep the Secure-cookie default, terminate HTTPS at the trusted proxy, and configure the actual public Origin. If TLS terminates in another proxy, configure forwarded scheme/host trust deliberately; do not trust arbitrary client-supplied forwarding headers. Public ingress should expose only HTTPS/HTTP redirect, with application/database ports private. Domain routing, TLS, host firewall rules, registry deployment and scheduled off-host backups remain deployment tasks.

Reference: [OAuth2 Proxy GitHub provider](https://oauth2-proxy.github.io/oauth2-proxy/configuration/providers/github/).
