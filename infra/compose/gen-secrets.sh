#!/usr/bin/env bash
# Generate local secrets for compose. Output is gitignored. Replace with
# SOPS/age (infra/secrets) before any host that is not your laptop.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
umask 077
mkdir -p generated ../edge/tls

rand() { openssl rand -hex 24; }

upsert_kv() {
  python3 - "$1" "$2" <<'PY'
import pathlib, re, sys
key, value = sys.argv[1], sys.argv[2]
path = pathlib.Path("generated/app.env")
text = path.read_text() if path.exists() else ""
line = f"{key}={value}"
pat = re.compile(rf"^{re.escape(key)}=.*$", re.M)
if pat.search(text):
    text = pat.sub(line, text, count=1)
else:
    if text and not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
path.write_text(text)
PY
}

if [[ ! -f generated/postgres_password ]]; then
  rand > generated/postgres_password
fi
pass=$(cat generated/postgres_password)
{
  printf '"jobcrm" "%s"\n' "${pass}"
  printf '"pgbouncer" "%s"\n' "$(rand)"
} > generated/userlist.txt

if [[ ! -f generated/grafana_admin_password ]]; then
  rand > generated/grafana_admin_password
fi

if [[ ! -f generated/app.env ]]; then
  fernet=$(python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
  cat > generated/app.env <<EOF
# Copied at deploy. Never commit.
TOKEN_FERNET_KEY=${fernet}
# OPENAI_API_KEY=
# TELEGRAM_API_ID=
# TELEGRAM_API_HASH=
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
# GOOGLE_REDIRECT_URI=https://your.domain/api/google/callback
# ALLOW_ORIGINS=https://your.domain
EOF
else
  if ! grep -q '^TOKEN_FERNET_KEY=' generated/app.env; then
    fernet=$(python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    printf 'TOKEN_FERNET_KEY=%s\n' "${fernet}" >> generated/app.env
  fi
fi

# Hex password is URL-safe. Always rewrite so pgbouncer userlist and DSN match.
upsert_kv DATABASE_URL "postgresql+asyncpg://jobcrm:${pass}@pgbouncer:6432/jobcrm"
upsert_kv DATABASE_MIGRATE_URL "postgresql+asyncpg://jobcrm:${pass}@postgres:5432/jobcrm"

if [[ ! -f ../edge/tls/origin.key ]]; then
  # ECDSA P-256: nginx 1.27 + OpenSSL 3. Self-signed is for bring-up and
  # Cloudflare Full (not Strict). Replace with a Cloudflare Origin CA cert
  # before pointing a real hostname here.
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
    -days 825 -nodes \
    -keyout ../edge/tls/origin.key \
    -out ../edge/tls/origin.crt \
    -subj "/CN=origin.workfinding.internal"
fi

chmod 600 generated/* ../edge/tls/origin.key
chmod 644 ../edge/tls/origin.crt
echo "wrote $(pwd)/generated and origin TLS (self-signed)"
echo "compose DATABASE_URL now points at pgbouncer (Postgres)."
echo "binds default to 10.7.0.1 (WireGuard). Laptop overlay binds 127.0.0.1."
