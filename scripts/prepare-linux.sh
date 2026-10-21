#!/bin/sh
# Run once on a fresh Ubuntu LTS or Debian 13 VM: sudo sh scripts/prepare-linux.sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo on the lab VM" >&2
    exit 1
fi
. /etc/os-release
case "$ID:$VERSION_ID:${VERSION_CODENAME:-}" in
    ubuntu:24.04:noble|ubuntu:26.04:resolute|debian:13:trixie) ;;
    *) echo "Supported hosts: Ubuntu 24.04/26.04 LTS or Debian 13" >&2; exit 1 ;;
esac
apt-get update
apt-get install -y ca-certificates curl git python3 qemu-guest-agent
install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: $VERSION_CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# Requires the Proxmox guest-agent channel; do not fail provisioning without it.
systemctl enable qemu-guest-agent
systemctl start qemu-guest-agent || echo "Enable the QEMU guest agent in Proxmox, then start the service."
docker version
docker compose version
