#!/usr/bin/env bash
# 07 — Docker CE from download.docker.com. Distro docker.io lags and ships iptables-legacy surprises.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

[[ ${ENABLE_DOCKER:-1} == 1 ]] || { log "07-docker: skipped"; exit 0; }

id=$(os_id)
codename=$(os_codename)
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL "https://download.docker.com/linux/${id}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${id} ${codename} stable" \
  > /etc/apt/sources.list.d/docker.list

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

install_file 0644 root root \
  "${FILES_DIR}/docker/daemon.json" \
  /etc/docker/daemon.json

# icc:false requires explicit --network. Compose files in infra/compose already do that.
usermod -aG docker "${ADMIN_USER:?set ADMIN_USER}"

systemctl enable --now docker
docker info >/dev/null
log "07-docker: $(docker version --format '{{.Server.Version}}')"
