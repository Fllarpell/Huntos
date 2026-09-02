#!/usr/bin/env bash
# Shared helpers. Sourced by every bootstrap stage. Not executable on its own.
set -euo pipefail

log()  { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
warn() { printf '[%s] WARN %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die()  { printf '[%s] FATAL %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; exit 1; }

require_root() {
  [[ ${EUID} -eq 0 ]] || die "run as root (sudo -E ./bootstrap.sh)"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

backup_file() {
  local src=$1
  [[ -f ${src} ]] || return 0
  local dst="${src}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  cp -a -- "${src}" "${dst}"
  log "backed up ${src} -> ${dst}"
}

install_file() {
  # install_file MODE OWNER GROUP SRC DST
  local mode=$1 owner=$2 group=$3 src=$4 dst=$5
  install -D -m "${mode}" -o "${owner}" -g "${group}" -- "${src}" "${dst}"
}

detect_public_iface() {
  # Default route interface. Fail closed — never guess "eth0".
  local iface
  iface=$(ip -4 route show default 0.0.0.0/0 2>/dev/null | awk '{print $5; exit}')
  [[ -n ${iface} ]] || die "cannot detect default IPv4 interface; set PUBLIC_IFACE"
  printf '%s\n' "${iface}"
}

os_id() {
  # shellcheck source=/dev/null
  . /etc/os-release
  printf '%s\n' "${ID}"
}

os_codename() {
  # shellcheck source=/dev/null
  . /etc/os-release
  printf '%s\n' "${VERSION_CODENAME}"
}

assert_supported_os() {
  local id codename
  id=$(os_id)
  codename=$(os_codename)
  case "${id}:${codename}" in
    ubuntu:noble|ubuntu:jammy|debian:bookworm|debian:trixie) ;;
    *) die "unsupported OS ${id}:${codename}. Pin Ubuntu 24.04 (noble) for this tree." ;;
  esac
}

reload_sysctl() {
  sysctl --system >/dev/null
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FILES_DIR="${SCRIPT_DIR}/files"
GENERATED_DIR="${SCRIPT_DIR}/generated"
mkdir -p "${GENERATED_DIR}"
chmod 700 "${GENERATED_DIR}"
