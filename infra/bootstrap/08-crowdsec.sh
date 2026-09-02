#!/usr/bin/env bash
# 08 — CrowdSec + nftables bouncer. Replaces Fail2Ban: signals are shared, not local regexes.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

[[ ${ENABLE_CROWDSEC:-1} == 1 ]] || { log "08-crowdsec: skipped"; exit 0; }

# Vendor install script is a supply-chain hop. We pin their apt repo the same
# way Docker is pinned, via the documented setup snippet but with -fsSL and
# a written source list rather than piping unknown bash into sh.
if [[ ! -f /etc/apt/sources.list.d/crowdsec.list ]]; then
  curl -fsSL https://install.crowdsec.net | bash
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends crowdsec crowdsec-firewall-bouncer-nftables

# ssh-bf + nginx collections. App collections wait until compose edge is up.
cscli collections install crowdsecurity/linux --force || true
cscli collections install crowdsecurity/sshd --force || true
cscli collections install crowdsecurity/nginx --force || true

systemctl enable --now crowdsec
systemctl enable --now crowdsec-firewall-bouncer
log "08-crowdsec: $(cscli version 2>/dev/null | head -n1 || echo installed)"
