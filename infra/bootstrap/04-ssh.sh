#!/usr/bin/env bash
# 04 — admin user + sshd hardening. Stays on SSH_PORT (default 22) until lockdown.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

: "${ADMIN_USER:?set ADMIN_USER}"
: "${ADMIN_SSH_PUBKEY:?set ADMIN_SSH_PUBKEY}"
: "${SSH_PORT:=22}"
: "${LOCKDOWN:=0}"

id -u "${ADMIN_USER}" >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo "${ADMIN_USER}"
install -d -m 0700 -o "${ADMIN_USER}" -g "${ADMIN_USER}" "/home/${ADMIN_USER}/.ssh"
AUTH_KEYS="/home/${ADMIN_USER}/.ssh/authorized_keys"

umask 077
{
  printf '%s\n' "${ADMIN_SSH_PUBKEY}"
  if [[ -n ${ADMIN_SSH_PUBKEY_EXTRA:-} ]]; then
    printf '%s\n' "${ADMIN_SSH_PUBKEY_EXTRA}"
  fi
} > "${AUTH_KEYS}"
chown "${ADMIN_USER}:${ADMIN_USER}" "${AUTH_KEYS}"
chmod 600 "${AUTH_KEYS}"

grep -qE '^ssh-ed25519 ' "${AUTH_KEYS}" || die "authorized_keys has no ssh-ed25519 line"
if grep -vE '^(ssh-ed25519 |#|$)' "${AUTH_KEYS}" | grep -q .; then
  die "authorized_keys contains a non-Ed25519 key; refused"
fi

# Host key: keep Ed25519, disable RSA/ECDSA so the algorithm policy is honest.
ssh-keygen -A
rm -f /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_rsa_key.pub \
      /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_ecdsa_key.pub \
      /etc/ssh/ssh_host_dsa_key /etc/ssh/ssh_host_dsa_key.pub
[[ -f /etc/ssh/ssh_host_ed25519_key ]] || die "sshd has no Ed25519 host key"

install_file 0644 root root \
  "${FILES_DIR}/ssh/99-hardening.conf" \
  /etc/ssh/sshd_config.d/99-hardening.conf

LISTEN_FILE=/etc/ssh/sshd_config.d/10-listen.conf
if [[ ${LOCKDOWN} == 1 ]]; then
  : "${WG_ADDRESS:=10.7.0.1/24}"
  WG_IP=${WG_ADDRESS%%/*}
  : "${SSH_LOCKDOWN_PORT:=2222}"
  cat > "${LISTEN_FILE}" <<EOF
Port ${SSH_LOCKDOWN_PORT}
ListenAddress ${WG_IP}
AllowUsers ${ADMIN_USER}
EOF
else
  cat > "${LISTEN_FILE}" <<EOF
Port ${SSH_PORT}
ListenAddress 0.0.0.0
AllowUsers ${ADMIN_USER}
EOF
fi
chmod 644 "${LISTEN_FILE}"

sshd -t
systemctl reload ssh || systemctl reload sshd
log "04-ssh: user=${ADMIN_USER} lockdown=${LOCKDOWN} (sshd -t ok)"
