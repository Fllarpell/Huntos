#!/usr/bin/env bash
# Restore drill: take the newest local backup, restore to a temp dir, integrity_check.
# Does not touch the live DB. Exit 1 if there is nothing to restore.
set -euo pipefail
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
WORKDIR=${BACKUP_WORKDIR:-/var/backups/workfinding}
latest=$(find "${WORKDIR}" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
[[ -n ${latest} ]] || { echo "no backups in ${WORKDIR}; run backup.sh first" >&2; exit 1; }

scratch=$(mktemp -d)
trap 'rm -rf "${scratch}"' EXIT

if [[ -f ${latest}/jobcrm.db ]]; then
  cp -a "${latest}/jobcrm.db" "${scratch}/jobcrm.db"
  sqlite3 "${scratch}/jobcrm.db" "PRAGMA integrity_check;" | grep -qx ok
  echo "sqlite restore drill ok from ${latest}"
fi

if [[ -f ${latest}/jobcrm.dump ]]; then
  echo "postgres dump present (${latest}/jobcrm.dump) — restore with pg_restore into a throwaway DB, not implemented here until asyncpg cutover"
fi

if [[ -f ${ROOT}/infra/backup/restic.env ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT}/infra/backup/restic.env"
  set +a
  restic check
  echo "restic check ok"
fi
