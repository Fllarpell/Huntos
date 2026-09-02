#!/usr/bin/env bash
# Pull Cloudflare IPv4/IPv6 prefixes and write set_real_ip_from lines.
# Fail closed: if curl fails, keep the previous file (do not empty it).
set -euo pipefail
out="$(cd "$(dirname "$0")" && pwd)/conf.d/00-realip.conf"
tmp=$(mktemp)
trap 'rm -f "${tmp}"' EXIT

{
  echo "# Generated $(date -u +%FT%TZ). Do not edit."
  echo "real_ip_header CF-Connecting-IP;"
  echo "real_ip_recursive on;"
  curl -fsSL https://www.cloudflare.com/ips-v4 | awk '{print "set_real_ip_from " $1 ";"}'
  curl -fsSL https://www.cloudflare.com/ips-v6 | awk '{print "set_real_ip_from " $1 ";"}'
} > "${tmp}"

grep -q 'set_real_ip_from' "${tmp}" || { echo "refusing to overwrite: empty CF list" >&2; exit 1; }
install -m 0644 "${tmp}" "${out}"
echo "wrote ${out}"
