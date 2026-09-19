#!/bin/sh
# Run explicitly as root on a freshly provisioned Guten Ubuntu 24.04 host.
set -eu
[ "$(id -u)" = 0 ]
. /etc/os-release
[ "$ID:$VERSION_ID" = ubuntu:24.04 ]
[ "$(dpkg --print-architecture)" = amd64 ]
case "$(cat /etc/guten/host-role)" in application|database) ;; *) exit 1;; esac
if command -v docker >/dev/null 2>&1; then
    echo 'Docker already installed; refusing an implicit upgrade.'
    docker version
    exit 0
fi
# Do not silently remove conflicting software on an existing host.
for package in docker.io podman-docker containerd runc; do
    if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
        echo "Conflicting package: $package" >&2; exit 1
    fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
install -d -m 0755 /etc/apt/keyrings
key=$(mktemp)
trap 'rm -f "$key"' EXIT
curl --fail --silent --show-error --location https://download.docker.com/linux/ubuntu/gpg -o "$key"
gpg --show-keys --with-colons "$key" | grep -q '^fpr:::::::::9DC858229FC7DD38854AE2D88D81803C0EBFCD88:'
install -m 0644 "$key" /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<'REPO'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
REPO
install -d -m 0755 /etc/docker
# Avoid overwriting administrator configuration.
[ ! -e /etc/docker/daemon.json ]
printf '%s\n' '{"log-driver":"local","log-opts":{"max-size":"10m","max-file":"3"},"live-restore":true}' > /etc/docker/daemon.json
apt-get update
# Versions verified together on the two Guten hosts; update deliberately.
apt-get install -y --no-install-recommends \
  docker-ce=5:29.8.1-1~ubuntu.24.04~noble \
  docker-ce-cli=5:29.8.1-1~ubuntu.24.04~noble \
  containerd.io=2.3.5-1~ubuntu.24.04~noble \
  docker-buildx-plugin=0.37.1-1~ubuntu.24.04~noble \
  docker-compose-plugin=5.5.1-1~ubuntu.24.04~noble
systemctl enable --now docker
install -d -m 0755 /var/lib/guten
# Record installed versions for subsequent hosts; upgrades are an explicit activity.
dpkg-query -W -f='${Package}=${Version}\n' docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin > /var/lib/guten/docker-packages.txt
docker version
docker compose version
