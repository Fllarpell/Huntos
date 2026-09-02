#!/usr/bin/env bash
# 05 — nftables. Default-drop input. SSH rule depends on LOCKDOWN.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

: "${WG_IFACE:=wg0}"
: "${WG_PORT:=51820}"
: "${SSH_PORT:=22}"
: "${SSH_LOCKDOWN_PORT:=2222}"
: "${LOCKDOWN:=0}"
PUBLIC_IFACE=${PUBLIC_IFACE:-$(detect_public_iface)}

if [[ ${LOCKDOWN} == 1 ]]; then
  SSH_RULE="iifname \"${WG_IFACE}\" tcp dport ${SSH_LOCKDOWN_PORT} ct state new accept"
else
  # Temporary: public key-only SSH so the first session survives a WG misconfig.
  SSH_RULE="tcp dport ${SSH_PORT} ct state new accept"
fi

tmp=$(mktemp)
trap 'rm -f "${tmp}"' EXIT
sed \
  -e "s|__PUBLIC_IFACE__|${PUBLIC_IFACE}|g" \
  -e "s|__WG_IFACE__|${WG_IFACE}|g" \
  -e "s|__WG_PORT__|${WG_PORT}|g" \
  -e "s|__SSH_PORT__|${SSH_PORT}|g" \
  -e "s|__LOCKDOWN__|${LOCKDOWN}|g" \
  -e "s|__SSH_RULE__|${SSH_RULE}|g" \
  "${FILES_DIR}/nftables/nftables.conf.tmpl" > "${tmp}"

nft -c -f "${tmp}" || die "nftables config failed dry-run"
backup_file /etc/nftables.conf
install -m 0644 "${tmp}" /etc/nftables.conf
systemctl enable nftables
nft -f /etc/nftables.conf
log "05-nftables: iface=${PUBLIC_IFACE} lockdown=${LOCKDOWN}"
