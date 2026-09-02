#!/usr/bin/env bash
# Produce a nocloud user-data file from bootstrap.env. Never commits the result.
#
#   cp infra/bootstrap/bootstrap.env.example /root/bootstrap.env
#   REPO_URL=git@github.com:you/work_finding.git REPO_REF=main \
#     ./infra/cloud-init/render.sh /root/bootstrap.env
#
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ENV_FILE=${1:-/root/bootstrap.env}
[[ -f ${ENV_FILE} ]] || { echo "missing ${ENV_FILE}" >&2; exit 1; }

set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a

: "${ADMIN_USER:?}"
: "${ADMIN_SSH_PUBKEY:?}"
: "${WG_CLIENT_PUBKEY:?}"
: "${REPO_URL:?set REPO_URL to the git remote this box should clone}"
REPO_REF=${REPO_REF:-main}
WG_CLIENT_ADDRESS=${WG_CLIENT_ADDRESS:-10.7.0.2/32}
WG_ADDRESS=${WG_ADDRESS:-10.7.0.1/24}
WG_PORT=${WG_PORT:-51820}
SSH_PORT=${SSH_PORT:-22}
SSH_LOCKDOWN_PORT=${SSH_LOCKDOWN_PORT:-2222}
ENABLE_CROWDSEC=${ENABLE_CROWDSEC:-1}
ENABLE_DOCKER=${ENABLE_DOCKER:-1}

umask 077
mkdir -p generated
OUT=generated/user-data.yaml
# envsubst only replaces $VAR / ${VAR}. Template uses ${ADMIN_USER} etc.
export ADMIN_USER ADMIN_SSH_PUBKEY WG_CLIENT_PUBKEY WG_CLIENT_ADDRESS \
  WG_ADDRESS WG_PORT SSH_PORT SSH_LOCKDOWN_PORT ENABLE_CROWDSEC ENABLE_DOCKER \
  REPO_URL REPO_REF
if command -v envsubst >/dev/null 2>&1; then
  envsubst < user-data.yaml.tmpl > "${OUT}"
else
  python3 - "$OUT" <<'PY'
import os
import pathlib
import sys

tmpl = pathlib.Path("user-data.yaml.tmpl").read_text()
pathlib.Path(sys.argv[1]).write_text(os.path.expandvars(tmpl))
PY
fi
chmod 600 "${OUT}"
echo "wrote $(pwd)/${OUT}"
echo "attach as --user-data-from-file (Hetzner) or nocloud. Do not run lockdown from cloud-init."
