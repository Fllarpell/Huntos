#!/usr/bin/env bash
# 01 — base packages + AppArmor. No docker/crowdsec here (those have their own repos).
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"

require_root
assert_supported_os

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg jq \
  chrony \
  auditd audispd-plugins \
  apparmor apparmor-utils \
  nftables \
  wireguard wireguard-tools \
  unattended-upgrades apt-listchanges \
  uidmap dbus-user-session \
  vim-tiny less htop \
  acl openssl

apt-get install -y --no-install-recommends rng-tools5 \
  || apt-get install -y --no-install-recommends rng-tools

# AppArmor must be enforcing before we put workloads on the box.
aa-status >/dev/null 2>&1 || warn "apparmor userspace present; reboot may be required if the kernel param is missing"
if grep -q 'apparmor=0' /proc/cmdline; then
  die "kernel cmdline disables AppArmor (apparmor=0). Fix GRUB and reboot."
fi

log "01-packages: ok"
