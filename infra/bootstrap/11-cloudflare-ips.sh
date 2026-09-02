#!/usr/bin/env bash
# Install the Cloudflare real_ip timer. Safe to run before nginx exists —
# the first tick writes 00-realip.conf; HUP is ignored if compose is down.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

UNIT_DIR=/etc/systemd/system
install_file 0644 root root \
  "${SCRIPT_DIR}/../systemd/cloudflare-realip.service" \
  "${UNIT_DIR}/cloudflare-realip.service"
install_file 0644 root root \
  "${SCRIPT_DIR}/../systemd/cloudflare-realip.timer" \
  "${UNIT_DIR}/cloudflare-realip.timer"

# First populate fail-closed file so a later nginx start has prefixes.
if [[ -x ${SCRIPT_DIR}/../edge/nginx/fetch-cloudflare-ips.sh ]]; then
  "${SCRIPT_DIR}/../edge/nginx/fetch-cloudflare-ips.sh" || warn "CF prefix fetch failed (offline?); nginx will not trust CF-Connecting-IP until it succeeds"
fi

systemctl daemon-reload
systemctl enable --now cloudflare-realip.timer
log "11-cloudflare-ips: timer enabled"
