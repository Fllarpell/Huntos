#!/usr/bin/env bash
# Local + optional offsite backup. SQLite is the live DB until asyncpg cutover.
# Offsite: set RESTIC_REPOSITORY + RESTIC_PASSWORD in restic.env (gitignored).
# Object Lock/WORM is a bucket property — this script cannot enable it; create
# the B2/S3 bucket with compliance retention before the first restic init.
#
#   sudo ./infra/backup/backup.sh
#
set -euo pipefail
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
WORKDIR=${BACKUP_WORKDIR:-/var/backups/workfinding}
umask 077
mkdir -p "${WORKDIR}/${STAMP}"
DEST="${WORKDIR}/${STAMP}"

sqlite_src=${SQLITE_PATH:-${ROOT}/backend/data/jobcrm.db}
if [[ -f ${sqlite_src} ]]; then
  if command -v sqlite3 >/dev/null; then
    sqlite3 "${sqlite_src}" ".backup '${DEST}/jobcrm.db'"
  else
    cp -a "${sqlite_src}" "${DEST}/jobcrm.db"
  fi
  sqlite3 "${DEST}/jobcrm.db" "PRAGMA integrity_check;" | grep -qx ok \
    || { echo "sqlite integrity_check failed" >&2; exit 1; }
  echo "sqlite -> ${DEST}/jobcrm.db"
else
  echo "no sqlite at ${sqlite_src} (ok on a fresh box)"
fi

if command -v docker >/dev/null; then
  pg_id=$(docker compose -f "${ROOT}/infra/compose/compose.yaml" --profile data ps -q postgres 2>/dev/null || true)
  if [[ -n ${pg_id} ]]; then
    docker compose -f "${ROOT}/infra/compose/compose.yaml" --profile data exec -T postgres \
      pg_dump -U jobcrm -d jobcrm -Fc > "${DEST}/jobcrm.dump"
    echo "postgres dump -> ${DEST}/jobcrm.dump"
  fi
fi

if [[ -f ${ROOT}/infra/backup/restic.env ]]; then
  # shellcheck source=/dev/null
  set -a && source "${ROOT}/infra/backup/restic.env" && set +a
  command -v restic >/dev/null || { echo "restic.env present but restic binary missing" >&2; exit 1; }
  restic snapshots >/dev/null 2>&1 || restic init
  restic backup "${DEST}" --tag workfinding --tag "${STAMP}"
  restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
  echo "restic snapshot ${STAMP}"
fi

# Drop local copies older than 14d — restic (if configured) is the offsite copy.
find "${WORKDIR}" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "ok ${DEST}"
