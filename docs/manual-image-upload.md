# Manual image uploads from a Mac to Guten

This is the interim operator procedure while Portal uploads and S3 media storage are deferred. It uses SSH/SCP, keeps images outside Docker images, preserves root ownership and read-only container mounts, and supports both single-file replacements and separate versioned media updates.

Verified against the host configuration and Next.js source on September 19, 2026. The commands below are a procedure for your next real upload; no production media was changed while writing this guide. They are intended for the existing trusted Guten operator, not a restricted contributor account.

## What to expect

Upload to a private staging folder as `ubuntu`, then use `sudo` for installation. Do not loosen `/srv/guten` permissions or grant Docker membership to make copying easier.

- **Replace an existing filename:** use the single-file procedure below. Only that file is replaced and backed up. No restart or Publish is needed; the change affects live content immediately.
- **Add new filenames / switch a complete media version:** use step 3. This conservative procedure copies the active media and recreates Sites and Portal, causing a brief frontend interruption. Next.js inventories public filenames at startup; that restriction does not apply to replacing the bytes of an already known filename.

Neither procedure builds application images or changes the database. No GitHub push, new AWS resource or AWS CLI login is needed.

## 1. Connect from the Mac

Open a Bash terminal. Use the existing local checkout and dedicated key:

```bash
cd /Users/samseatt/projects/guten/guten
GUTEN_SSH_OPTIONS=(-F /dev/null -o BatchMode=yes -o ConnectTimeout=15 \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$PWD/.cloud-provision/known_hosts" \
  -i "$PWD/.cloud-provision/guten-cloud")
ssh "${GUTEN_SSH_OPTIONS[@]}" ubuntu@52.54.75.169
```

This is the **app host**, `guten-app-01`. Do not upload to the database host. In the remote shell you can run `df -h /srv/guten` and `readlink -f /srv/guten/assets` to inspect space and the active media directory. Run `exit` to return to the Mac before using SCP.

SSH is allowed only from the approved administrator public IP. A timeout after changing networks may require an authorized operator to update Lightsail's SSH source rule to your current public IPv4 `/32`. Do not open SSH to everyone. `Permission denied (publickey)` calls for checking the key and `ubuntu` username. A host-key mismatch requires verifying the server identity; do not disable host-key checking or blindly erase the pinned entry. Keep the key out of Git/chat.

## 2. Stage the image and verify transfer

Example: your new file is `~/Pictures/welcome-v2.png`, to be used as `/assets/fieldnotes/welcome-v2.png`. Substitute your own site folder and filename consistently below. Use simple lowercase names, digits and hyphens, with no spaces. The folder is a convention to avoid collisions, not an access restriction.

In the **same Mac terminal** (so the SSH options remain defined):

```bash
file "$HOME/Pictures/welcome-v2.png"
shasum -a 256 "$HOME/Pictures/welcome-v2.png"
ssh "${GUTEN_SSH_OPTIONS[@]}" ubuntu@52.54.75.169 \
  'install -d -m 0700 /home/ubuntu/guten-upload'
scp "${GUTEN_SSH_OPTIONS[@]}" "$HOME/Pictures/welcome-v2.png" \
  ubuntu@52.54.75.169:/home/ubuntu/guten-upload/welcome-v2.png
ssh "${GUTEN_SSH_OPTIONS[@]}" ubuntu@52.54.75.169 \
  'sha256sum /home/ubuntu/guten-upload/welcome-v2.png'
```

Confirm the two hashes match and the file is the intended image. Use trusted PNG/JPEG/WebP files; this manual workflow is not an untrusted upload validator. A large image also affects page load time, so resize/compress it before uploading if appropriate. Do not copy an entire Pictures folder.

## Replace one existing image without changing its name

Use this path for small, frequent image swaps. It replaces **only that image**, retaining one backup of the old file outside the public assets tree. It does not copy the media directory, change its symlink, rebuild images, restart containers or require Publish. All draft and published pages using that path see the replacement as their caches refresh. This immediate public change is intentional for this workflow.

Follow steps 1–2 above to stage the replacement and compare its hash. Keep the same filename, image format and extension. Then connect to the app host and run the following, editing `relative`, `staged` and `expected` first. The target must already exist. For an entirely new filename, use the separate new-version procedure below.

```bash
sudo python3 - <<'PY'
from pathlib import Path, PurePosixPath
import datetime, fcntl, hashlib, json, os, shutil, tempfile

relative = 'fieldnotes/welcome.png'
staged = Path('/home/ubuntu/guten-upload/welcome.png')
expected = 'REPLACE_WITH_64_CHARACTER_SHA256_FROM_MAC'

assert len(expected) == 64 and all(c in '0123456789abcdef' for c in expected)
assert relative and not PurePosixPath(relative).is_absolute()
assert all(p not in ('', '.', '..') for p in relative.split('/'))
assert '\\' not in relative
with open('/var/lib/guten/deployments/lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assets = Path('/srv/guten/assets').resolve(strict=True)
    target = assets / relative
    assert target.is_file() and not target.is_symlink(), 'Existing regular image required'
    assert target.resolve().is_relative_to(assets), 'Target escapes assets'
    assert staged.is_file() and not staged.is_symlink(), 'Regular staged file required'
    backup_root = Path('/srv/guten/media-overwrite-backups')
    backup_root.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')
    backup = Path(tempfile.mkdtemp(prefix=stamp, dir=backup_root))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.upload-', delete=False) as out:
            temporary = Path(out.name)
            with staged.open('rb') as source:
                shutil.copyfileobj(source, out)
            out.flush()
            os.fsync(out.fileno())
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest(temporary) == expected, 'Uploaded checksum does not match'
        old_hash = digest(target)
        shutil.copy2(target, backup / 'original')
        assert digest(backup / 'original') == old_hash, 'Backup verification failed'
        (backup / 'receipt.json').write_text(json.dumps({
            'target': str(target), 'relative': relative,
            'previous_sha256': old_hash, 'replacement_sha256': expected,
        }, indent=2) + '\n')
        os.chown(temporary, 0, 0)
        temporary.chmod(0o644)
        os.replace(temporary, target)
        temporary = None
        print('Replaced:', target)
        print('Single-file backup:', backup)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
PY
```

The rename is atomic: readers receive the old complete file or the new complete file, not a half-copied upload. Root ownership and container read-only mounts remain unchanged. The running frontends already know this filename, so no restart is needed.

Use step 4's download/hash check with the **unchanged path**. If the browser still shows old artwork, hard-refresh or test with a temporary query suffix such as `?check=20260919`. Browser/intermediary caches can delay visibility; a normal client refresh is not proof that the server still holds old bytes. Check the downloaded hash before making another replacement.

To undo, stage the saved `original` as your replacement file and run this same procedure with its `previous_sha256` from `receipt.json`. This backs up the current image before restoring the old one. Do not restore a database or switch the entire media directory to undo a single-file replacement.

Archive the originals/receipts with your media backups. Each successful swap adds only the replaced file's size plus a small receipt. After verifying and independently archiving them, remove specifically selected old backup directories as needed; there is no automatic retention job for these manual backups. Do not delete the active assets tree. Same-name replacements change the active version's bytes, so its original bundle manifest/checksum becomes historical; future inventories must hash the current files rather than assume the initial directory name still describes them.

## 3. Install a new media version (new filenames)

Connect again with the SSH command above. The following block runs **on the app host**. Edit its three configuration values: site folder, image filename and expected SHA256 from the Mac. It refuses to replace an existing filename, so a new artwork revision does not silently change a currently published image.

Coordinate with other operators before starting. The block holds the same deployment lock as the release tool. It copies the current media, installs the image, records its origin and checksum, atomically switches the symlink, and recreates only the two frontends. Stop and inspect any error; do not continue by removing checks.

```bash
sudo bash <<'SH'
set -euo pipefail
site_folder='fieldnotes'
image_file='welcome-v2.png'
expected_sha256='REPLACE_WITH_64_CHARACTER_SHA256_FROM_MAC'

[[ "$site_folder" =~ ^[a-z0-9][a-z0-9_-]*$ ]]
[[ "$image_file" =~ ^[a-z0-9][a-z0-9._-]*\.(png|jpg|jpeg|webp)$ ]]
[[ "$expected_sha256" =~ ^[a-f0-9]{64}$ ]]
exec 9>/var/lib/guten/deployments/lock
flock -n 9
release=$(python3 - <<'PY'
import json,re
from pathlib import Path
state=json.loads(Path('/var/lib/guten/deployments/state.json').read_text())
assert state['outcome']=='healthy', 'Inspect deployment state before a media update'
name=state['last_successful']
assert re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',name)
print(name)
PY
)
compose="/opt/guten/releases/$release/compose.json"
test -f "$compose"
source_file="/home/ubuntu/guten-upload/$image_file"
test -f "$source_file" && test ! -L "$source_file"
previous=$(readlink -f /srv/guten/assets)
[[ "$previous" == /srv/guten/media/*/assets ]]
test -d "$previous"
version=$(mktemp -d /srv/guten/media/manual-XXXXXXXX)
chmod 0755 "$version"
printf 'Previous assets: %s\nNew media: %s\nRelease: %s\n' "$previous" "$version" "$release"
# Copy bytes, not hard links: the old version must remain unchanged.
cp -a "$previous" "$version/assets"
test ! -L "$version/assets/$site_folder"
install -d -o root -g root -m 0755 "$version/assets/$site_folder"
destination="$version/assets/$site_folder/$image_file"
test ! -e "$destination" && test ! -L "$destination"
install -o root -g root -m 0644 "$source_file" "$destination"
printf '%s  %s\n' "$expected_sha256" "$destination" | sha256sum --check -
printf 'previous_assets=%s\nrelease=%s\nasset=/assets/%s/%s\nsha256=%s\n' \
  "$previous" "$release" "$site_folder" "$image_file" "$expected_sha256" \
  > "$version/manual-update.txt"
chmod 0644 "$version/manual-update.txt"
ln -s "$version/assets" "$version/next-assets"
mv -Tf "$version/next-assets" /srv/guten/assets
docker compose -p guten-prod -f "$compose" up -d \
  --no-deps --no-build --pull never --force-recreate \
  --wait --wait-timeout 180 sites portal
printf 'Now verify the image and both frontends. Recovery record: %s/manual-update.txt\n' "$version"
SH
```

Save the printed new-media path and recovery record with your operational notes. The new `manual-*` directory has a `manual-update.txt` receipt; it does not claim to have the original bundle's full inventory manifest or archive checksum. The previous version remains intact. Before a future full media package, inventory the current files and current AWS draft/published references, including these manual additions.

If the command fails before the symlink switch, the old media stays active; an unused staging version may remain for inspection. If it fails after the switch, the frontends may be partially recreated. Use the recovery steps below rather than assuming the update rolled itself back. Deployment state tracks application releases and is not advanced by this media operation.

## 4. Verify, then use the image in Portal

On the Mac, replace the example filename with yours:

```bash
curl --fail --silent --show-error \
  https://guten.ink/assets/fieldnotes/welcome-v2.png \
  -o /tmp/guten-upload-check.png
shasum -a 256 /tmp/guten-upload-check.png
```

The downloaded hash should match the source. The shared file can be served through an already active publication such as Guten even if your new publication is not yet live. **These assets are public files, not confidential draft storage.** Open the image in a browser too.

Sign into Portal, enter `/assets/fieldnotes/welcome-v2.png` in the page's image field, save and use **View Draft** to verify it. Then Publish when ready and check the published page. Also verify an existing site's page and Portal dashboard after the frontend recreation. Refresh if the browser shows cached content. Never bypass certificate verification to obtain a passing test.

New filenames preserve the editorial boundary: old published pages keep their previous image until you publish the draft reference. Directly overwriting an old filename would bypass that boundary and can also leave browsers showing cached bytes. Use `v2`, `v3`, etc. when you want to preserve that editorial boundary. Use the single-file replacement procedure above when an immediate same-name public update is intended.

Archive your source file, installed version/receipt and relevant operational notes outside Git. Database dumps do not contain image bytes. Once verified and archived, the exact staging file in `/home/ubuntu/guten-upload/` can be removed. Do not delete old media versions or files still needed by either draft or published content as part of routine uploading.

## Recover an unsuccessful media switch

Do this before making or publishing content changes that depend on the new image. If such changes already happened, reverting media can break those references; coordinate the content correction too.

Read the new version's `manual-update.txt` and obtain `previous_assets` and `release`. In the following **remote-host** block, replace the two placeholders with those exact values. It verifies that the application release is still the same; if another deployment happened, stop for operator review instead of redeploying an old configuration accidentally.

```bash
sudo bash <<'SH'
set -euo pipefail
previous='/srv/guten/media/REPLACE_WITH_PREVIOUS_VERSION/assets'
release='REPLACE_WITH_RECORDED_RELEASE'
exec 9>/var/lib/guten/deployments/lock
flock -n 9
[[ "$previous" == /srv/guten/media/*/assets ]]
test -d "$previous"
python3 - "$release" <<'PY'
import json,sys
from pathlib import Path
state=json.loads(Path('/var/lib/guten/deployments/state.json').read_text())
assert state['outcome']=='healthy' and state['last_successful']==sys.argv[1]
PY
recovery_dir=$(mktemp -d /srv/guten/media/recovery-XXXXXXXX)
ln -s "$previous" "$recovery_dir/previous-assets"
mv -Tf "$recovery_dir/previous-assets" /srv/guten/assets
rmdir "$recovery_dir"
docker compose -p guten-prod -f "/opt/guten/releases/$release/compose.json" up -d \
  --no-deps --no-build --pull never --force-recreate \
  --wait --wait-timeout 180 sites portal
SH
```

Recheck the public site, images and authenticated Portal. Keep the failed media version for diagnosis. This procedure does not roll back database content, change DNS or restore a database. See [application releases](releases.md) for application rollback, which likewise does not undo media changes.

## Scope and future replacement

This is a temporary trusted-operator workflow. A proper Portal/S3 upload feature should replace the manual transport, staging and activation work while preserving stable content references and recovery. Until then, use single-file replacements for existing names and the versioned procedure for new filenames; ask the operator to batch multiple files into one reviewed media version and one frontend recreation when practical.
