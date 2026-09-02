#!/usr/bin/env bash
# Zero-touch host bring-up. Idempotent. Safe default does NOT lock public SSH.
#
#   cp bootstrap.env.example /root/bootstrap.env   # fill in
#   sudo -E ./bootstrap.sh                         # stage 1
#   # bring WG client up, ssh over 10.7.0.1
#   sudo -E ./bootstrap.sh --lockdown              # stage 2
#
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
source ./lib/common.sh
require_root
assert_supported_os

ENV_FILE=${BOOTSTRAP_ENV:-/root/bootstrap.env}
[[ -f ${ENV_FILE} ]] || ENV_FILE="${SCRIPT_DIR}/bootstrap.env"
[[ -f ${ENV_FILE} ]] || die "missing ${ENV_FILE} (copy bootstrap.env.example and fill ADMIN_SSH_PUBKEY + WG_CLIENT_PUBKEY)"
set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a

LOCKDOWN_ONLY=0
if [[ ${1:-} == --lockdown ]]; then
  LOCKDOWN_ONLY=1
  export LOCKDOWN=1
fi

export ADMIN_USER ADMIN_SSH_PUBKEY ADMIN_SSH_PUBKEY_EXTRA \
  PUBLIC_IFACE WG_IFACE WG_ADDRESS WG_PORT WG_CLIENT_PUBKEY WG_CLIENT_ADDRESS \
  SSH_PORT SSH_LOCKDOWN_PORT LOCKDOWN ENABLE_CROWDSEC ENABLE_DOCKER

if [[ ${LOCKDOWN_ONLY} == 1 ]]; then
  exec "${SCRIPT_DIR}/10-lockdown.sh"
fi

log "bootstrap: start os=$(os_id):$(os_codename) iface=${PUBLIC_IFACE:-auto}"
"${SCRIPT_DIR}/01-packages.sh"
"${SCRIPT_DIR}/02-sysctl.sh"
"${SCRIPT_DIR}/03-wireguard.sh"
"${SCRIPT_DIR}/04-ssh.sh"
"${SCRIPT_DIR}/05-nftables.sh"
"${SCRIPT_DIR}/06-audit-time.sh"
"${SCRIPT_DIR}/07-docker.sh"
"${SCRIPT_DIR}/08-crowdsec.sh"
"${SCRIPT_DIR}/09-unattended.sh"
"${SCRIPT_DIR}/11-cloudflare-ips.sh"
"${SCRIPT_DIR}/verify.sh"
log "bootstrap: stage-1 complete. Verify WG from the client, then: $0 --lockdown"
