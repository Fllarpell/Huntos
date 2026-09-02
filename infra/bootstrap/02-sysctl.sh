#!/usr/bin/env bash
# 02 — sysctl drop-in. Idempotent.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

install_file 0644 root root \
  "${FILES_DIR}/sysctl.d/99-workfinding.conf" \
  /etc/sysctl.d/99-workfinding.conf

# BBR is in-tree on 6.x. Fail if the module/builtin is missing rather than silently
# falling back to cubic (which we would not notice until a CF-origin incident).
if ! sysctl net.ipv4.tcp_available_congestion_control | grep -qw bbr; then
  modprobe tcp_bbr 2>/dev/null || true
fi
sysctl --system >/dev/null
sysctl -n net.ipv4.tcp_congestion_control | grep -qx bbr \
  || die "BBR did not activate (got $(sysctl -n net.ipv4.tcp_congestion_control))"

log "02-sysctl: BBR=$(sysctl -n net.ipv4.tcp_congestion_control) qdisc=$(sysctl -n net.core.default_qdisc)"
