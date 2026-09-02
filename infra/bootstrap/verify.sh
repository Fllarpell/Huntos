#!/usr/bin/env bash
# Non-destructive assertions. Exit 1 on any failed control. Safe to run often.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"

fail=0
check() {
  local name=$1
  shift
  if "$@"; then
    log "PASS  ${name}"
  else
    warn "FAIL  ${name}"
    fail=1
  fi
}

check "bbr" grep -qx bbr <<<"$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo x)"
check "syncookies" grep -qx 1 <<<"$(sysctl -n net.ipv4.tcp_syncookies 2>/dev/null || echo 0)"
check "kptr_restrict" grep -qx 2 <<<"$(sysctl -n kernel.kptr_restrict 2>/dev/null || echo 0)"
check "unprivileged_bpf_disabled" grep -qx 1 <<<"$(sysctl -n kernel.unprivileged_bpf_disabled 2>/dev/null || echo 0)"
check "nftables-unit" systemctl is-enabled nftables
check "sshd-config" sshd -t
check "root-ssh-disabled" grep -q '^PermitRootLogin no' /etc/ssh/sshd_config.d/99-hardening.conf
check "password-auth-disabled" grep -q '^PasswordAuthentication no' /etc/ssh/sshd_config.d/99-hardening.conf
check "wg-up" wg show "${WG_IFACE:-wg0}"
check "chrony" systemctl is-active chrony
check "auditd" systemctl is-active auditd
if [[ ${ENABLE_DOCKER:-1} == 1 ]] && command -v docker >/dev/null; then
  check "docker" docker info
  check "docker-icc-false" grep -q '"icc": false' /etc/docker/daemon.json
  check "docker-log-cap" grep -q '"max-size": "10m"' /etc/docker/daemon.json
fi
if [[ ${ENABLE_CROWDSEC:-1} == 1 ]] && command -v cscli >/dev/null; then
  check "crowdsec" systemctl is-active crowdsec
fi

if [[ ${fail} -ne 0 ]]; then
  die "verify: one or more controls failed"
fi
log "verify: all controls passed"
