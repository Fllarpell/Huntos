"""Copy sqlite rows into an empty postgres (after alembic upgrade).

Run inside compose — postgres is on an internal network and sqlite lives on
the backend_data volume:

  docker compose --profile data --profile app run --rm --no-deps \\
    -e DATABASE_URL_SRC=sqlite+aiosqlite:////data/jobcrm.db \\
    backend python -m scripts.sqlite_to_postgres

Exit 1 if any table row counts diverge.
"""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _sync_url(url: str) -> str:
    return (
        url.replace("sqlite+aiosqlite", "sqlite")
        .replace("postgresql+asyncpg", "postgresql+psycopg")
    )


def _ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"refusing identifier {name!r}")
    return name


def _reset_sequences(dst: Engine) -> None:
    with dst.begin() as dconn:
        rows = dconn.execute(
            text(
                """
                SELECT c.table_name, pg_get_serial_sequence(
                    format('%I.%I', c.table_schema, c.table_name), 'id'
                ) AS seq
                FROM information_schema.columns c
                WHERE c.table_schema = 'public'
                  AND c.column_name = 'id'
                  AND c.table_name <> 'alembic_version'
                """
            )
        )
        for table_name, seq in rows:
            if not seq:
                continue
            quoted = _ident(table_name)
            dconn.execute(
                text(
                    f"SELECT setval(CAST(:seq AS regclass), COALESCE((SELECT MAX(id) FROM {quoted}), 1))"
                ),
                {"seq": seq},
            )


def copy_all(src: Engine, dst: Engine) -> dict[str, tuple[int, int]]:
    src_meta = MetaData()
    src_meta.reflect(bind=src)
    dst_meta = MetaData()
    dst_meta.reflect(bind=dst)
    counts: dict[str, tuple[int, int]] = {}
    with dst.begin() as dconn:
        dconn.execute(text("SET session_replication_role = replica"))
        with src.connect() as sconn:
            for table in src_meta.sorted_tables:
                name = table.name
                if name not in dst_meta.tables or name == "alembic_version":
                    if name not in dst_meta.tables:
                        print(f"skip {name} (not in dest)")
                    continue
                rows = [dict(row._mapping) for row in sconn.execute(table.select())]
                if rows:
                    dconn.execute(dst_meta.tables[name].insert(), rows)
                quoted = _ident(name)
                n_src = sconn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one()
                n_dst = dconn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one()
                counts[name] = (int(n_src), int(n_dst))
                print(f"{name}: src={n_src} dst={n_dst}")
        dconn.execute(text("SET session_replication_role = DEFAULT"))
    _reset_sequences(dst)
    return counts


def main() -> None:
    src_url = os.environ.get("DATABASE_URL_SRC") or "sqlite+aiosqlite:////data/jobcrm.db"
    dst_url = os.environ.get("DATABASE_URL_DST") or os.environ.get("DATABASE_URL", "")
    if "sqlite" not in src_url:
        print("DATABASE_URL_SRC must be sqlite", file=sys.stderr)
        sys.exit(2)
    if "postgres" not in dst_url:
        print("DATABASE_URL_DST / DATABASE_URL must be postgres", file=sys.stderr)
        sys.exit(2)
    src = create_engine(_sync_url(src_url))
    dst = create_engine(_sync_url(dst_url))
    counts = copy_all(src, dst)
    src.dispose()
    dst.dispose()
    mismatched = {k: v for k, v in counts.items() if v[0] != v[1]}
    if mismatched:
        print(f"checksum mismatch: {mismatched}", file=sys.stderr)
        sys.exit(1)
    print("ok")


if __name__ == "__main__":
    main()
