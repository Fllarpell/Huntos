#!/usr/bin/env bash
# 03 — WireGuard server. Keys live in /etc/wireguard (mode 600), never in git.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

: "${WG_IFACE:=wg0}"
: "${WG_ADDRESS:=10.7.0.1/24}"
: "${WG_PORT:=51820}"
: "${WG_CLIENT_PUBKEY:?set WG_CLIENT_PUBKEY in bootstrap.env}"
: "${WG_CLIENT_ADDRESS:=10.7.0.2/32}"

umask 077
install -d -m 0700 /etc/wireguard
KEY_FILE="/etc/wireguard/${WG_IFACE}.key"
PUB_FILE="/etc/wireguard/${WG_IFACE}.pub"

if [[ ! -f ${KEY_FILE} ]]; then
  wg genkey | tee "${KEY_FILE}" | wg pubkey > "${PUB_FILE}"
  chmod 600 "${KEY_FILE}"
  chmod 644 "${PUB_FILE}"
  log "03-wireguard: generated ${KEY_FILE}"
fi

WG_PRIVATE_KEY=$(cat "${KEY_FILE}")
tmpl="${FILES_DIR}/wireguard/wg0.conf.tmpl"
conf="/etc/wireguard/${WG_IFACE}.conf"
sed \
  -e "s|__WG_ADDRESS__|${WG_ADDRESS}|g" \
  -e "s|__WG_PORT__|${WG_PORT}|g" \
  -e "s|__WG_PRIVATE_KEY__|${WG_PRIVATE_KEY}|g" \
  -e "s|__WG_CLIENT_PUBKEY__|${WG_CLIENT_PUBKEY}|g" \
  -e "s|__WG_CLIENT_ADDRESS__|${WG_CLIENT_ADDRESS}|g" \
  "${tmpl}" > "${conf}"
chmod 600 "${conf}"

systemctl enable --now "wg-quick@${WG_IFACE}"
wg show "${WG_IFACE}" >/dev/null

cp -a "${PUB_FILE}" "${GENERATED_DIR}/${WG_IFACE}.pub"
log "03-wireguard: server pubkey=$(cat "${PUB_FILE}")"
log "03-wireguard: client must use AllowedIPs ${WG_ADDRESS%/*}/24 Endpoint=<public-ip>:${WG_PORT}"
