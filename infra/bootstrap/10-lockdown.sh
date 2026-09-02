#!/usr/bin/env bash
# 10 — lockdown. Refuses unless WireGuard has a handshake in the last 3 minutes.
# Run from a *second* session over WG, not from the public SSH you are about to cut.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

: "${WG_IFACE:=wg0}"
: "${WG_ADDRESS:=10.7.0.1/24}"

wg show "${WG_IFACE}" >/dev/null 2>&1 || die "wg interface ${WG_IFACE} is down"
latest=$(wg show "${WG_IFACE}" latest-handshakes | awk 'NF==2 {print $2; exit}')
[[ -n ${latest} && ${latest} != 0 ]] || die "no WG handshake yet — connect the client first"
now=$(date +%s)
age=$((now - latest))
(( age < 180 )) || die "last WG handshake ${age}s ago (>180s). Connect over WG, then retry."

# Must be on the WG address already, otherwise we lock the operator out.
wg_ip=${WG_ADDRESS%%/*}
ss -tn | grep -q "${wg_ip}" || warn "no TCP session seen on ${wg_ip}; you may not be on WG"

export LOCKDOWN=1
"${SCRIPT_DIR}/04-ssh.sh"
"${SCRIPT_DIR}/05-nftables.sh"

# Disable password auth leftover units; sshd drop-in already forbids it.
passwd -l root
log "10-lockdown: sshd on ${wg_ip}:${SSH_LOCKDOWN_PORT:-2222}; public :22 dropped"
log "10-lockdown: keep this WG session open and open a NEW ssh -p ${SSH_LOCKDOWN_PORT:-2222} ${ADMIN_USER}@${wg_ip} before closing"
