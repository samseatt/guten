# App-host preparation before DNS cutover

The app host is `guten-app-01` at `52.54.75.169`. Use the existing dedicated SSH key and pinned known-hosts file under ignored `.cloud-provision/`. These steps operate on that host only; they do not provision resources, change DNS, alter the database or start public applications.

## Production credential files

```bash
python3 scripts/configure_cloud_app.py prepare
```

This creates missing files under ignored `.cloud-app/`, directory mode 0700 and file mode 0600. Existing values are preserved. Keep this directory private and archive it separately from Git.

- Create a classic GitHub token for `samseatt` with **only `read:packages`**, initially expiring after 90 days. Put it in `ghcr_read_token`, without quotes. Do not reuse the Mac's publishing token or log the Mac into this read-only token.
- Create **Guten Portal — Production**, an OAuth App with homepage `https://portal.guten.ink` and callback `https://portal.guten.ink/oauth2/callback`.
- Replace the quoted Client ID placeholder in `oauth2-proxy.cfg`. Put the separate Client secret in `github_client_secret`, without quotes.
- Leave the generated cookie key and reviewed config settings intact. Only `samseatt` is permitted to log in; Secure, HttpOnly cookies remain enabled.

After filling those files:

```bash
python3 scripts/configure_cloud_app.py install
```

The installer verifies the token's GitHub identity and exact scope set before transfer. It validates the OAuth config against the committed template, without displaying secret values. SSH transmits the files to `/etc/guten/secrets`; OAuth files are owned by root, group 65532, mode 0640. Matching installed files can be reused, but differing values require deliberate rotation instead of silent replacement.

The separate registry credential is passed to `docker login --password-stdin` on the host. Root's Docker configuration is restricted to mode 0600 inside a 0700 directory; Docker stores the credential there without encryption. Host access is therefore privileged, and this token must remain read-only. The installer prints expiry metadata if GitHub supplies it. Record the expiry and rotate before future image pulls need it. Never copy these files into images or release bundles.

Installation validates syntax and permissions; a successful real GitHub login still requires the production URL, TLS and a manual browser test.

## Media installation

The verified initial bundle is `artifacts/media-20260919.tar`, SHA256 `805cf186e13285efb280b7b6b25cd847da636859a2b3bf6c172897fc88ab4d89`. Transfer it and `scripts/install_media.py` over the pinned SSH connection into a private staging directory. On the host:

```bash
sudo python3 /home/ubuntu/guten-stage/install_media.py \
  --archive /home/ubuntu/guten-stage/media-20260919.tar \
  --sha256 805cf186e13285efb280b7b6b25cd847da636859a2b3bf6c172897fc88ab4d89
```

The installer checks the full archive before and after processing, every file's size/hash, and the exact manifest/member set. It rejects links, duplicates and unsafe paths. It never calls unrestricted tar extraction. Verified files are installed under `/srv/guten/media/<archive-sha256>/assets`, with a root-owned `/srv/guten/assets` symlink to that version. Files are 0644 and directories 0755. Symlink permissions display as 0777; write control belongs to the root-owned parent directory.

The initial installer refuses an existing active path or version. For subsequent media changes, plan an explicit switch and recreate the frontend containers so their bind mounts resolve the new version; retain previous media for rollback. Do not rerun this initial installer to overwrite live assets.

## Current evidence

On September 18, 2026, all 301 media files were installed successfully. The app host had roughly 74 GB free before installation. The local record is `artifacts/cloud-media-install-20260919.json`. The known missing Neubank favicon remains in the manifest; no content was edited. Root ownership and file readability were checked after installation.

`artifacts/images-initial-20260919.json` pins all seven images: four published private app images plus the locally tested OAuth2 Proxy, Nginx and Caddy digests. Credential installation, remote image pulls, release staging and real login verification are subsequent checkpoints, not implied by media installation.

Tests:

```bash
python3 -B -m unittest discover -s tests -p test_media_install.py -v
python3 -B -m unittest discover -s tests -p test_cloud_app_config.py -v
```

References: [GitHub registry authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [creating an OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
