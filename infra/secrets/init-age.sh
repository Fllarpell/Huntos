#!/usr/bin/env bash
# Generate an age identity (gitignored) and pin its public key in .sops.yaml.
# Private key never goes to git. Backup age.key to a password manager.
#
#   ./infra/secrets/init-age.sh
#   sops -e -i infra/secrets/secrets.yaml
#
set -euo pipefail
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
KEY="${ROOT}/infra/secrets/age.key"
SOPS_FILE="${ROOT}/.sops.yaml"
EXAMPLE="${ROOT}/infra/secrets/secrets.yaml.example"
LIVE="${ROOT}/infra/secrets/secrets.yaml"

command -v age-keygen >/dev/null || {
  echo "install age (brew install age / apt install age)" >&2
  exit 1
}

umask 077
if [[ ! -f ${KEY} ]]; then
  age-keygen -o "${KEY}"
  echo "wrote ${KEY}"
fi
PUB=$(age-keygen -y "${KEY}")
export PUB
python3 - "${SOPS_FILE}" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
pub = __import__("os").environ["PUB"].strip()
new, n = re.subn(r"age: age1\S+", f"age: {pub}", text, count=1)
if n != 1:
    raise SystemExit("could not patch .sops.yaml age recipient")
path.write_text(new)
print(f"pinned {pub} in {path}")
PY

if [[ ! -f ${LIVE} ]]; then
  cp "${EXAMPLE}" "${LIVE}"
  echo "copied secrets.yaml.example -> secrets.yaml (fill, then sops -e -i)"
fi
echo "SOPS_AGE_KEY_FILE=${KEY}"
echo "encrypt: SOPS_AGE_KEY_FILE=${KEY} sops -e -i ${LIVE}"
