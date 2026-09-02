#!/usr/bin/env bash
# 06 — chrony, rng-tools, auditd. Entropy: virtio-rng if present, else jitterentropy.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

install_file 0644 root root \
  "${FILES_DIR}/chrony/chrony.conf" \
  /etc/chrony/chrony.conf
systemctl enable --now chrony
chronyc waitsync 10 0.1 0 1 || warn "chrony not synced yet (ok on first boot behind a broken NTP ACL)"

# rng-tools5 reads /dev/hwrng. On AWS/GCP/Hetzner this is virtio-rng/Nitro.
# haveged is not installed: it is redundant on kernels with jitter entropy
# and fights the kernel pool on modern 6.x.
systemctl enable --now rngd 2>/dev/null || systemctl enable --now rng-tools 2>/dev/null || warn "rngd unit name differs; check systemctl status rngd"
entropy=$(cat /proc/sys/kernel/random/entropy_avail || echo 0)
log "06-time: entropy_avail=${entropy} (on modern kernels this counter stays low; urandom is still CSPRNG)"

install_file 0640 root root \
  "${FILES_DIR}/audit/99-workfinding.rules" \
  /etc/audit/rules.d/99-workfinding.rules
augenrules --load || true
systemctl enable --now auditd
log "06-audit: ok"
