from collections.abc import AsyncIterator

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATA_DIR, settings


class Base(DeclarativeBase):
    pass


def _resolve_sqlite_url(url: str) -> str:
    if "sqlite" not in url:
        return url
    prefix, sep, path = url.partition("///")
    if not sep:
        return url
    from pathlib import Path

    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = (DATA_DIR.parent / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}///{db_path}"


if settings.is_sqlite():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

_url = _resolve_sqlite_url(settings.database_url)
_engine_kwargs: dict = {"echo": False, "future": True}
if settings.is_sqlite():
    _engine_kwargs["connect_args"] = {"timeout": 60}
else:
    # Safe behind PgBouncer even if pool_mode is later switched to transaction.
    _engine_kwargs["connect_args"] = {"statement_cache_size": 0}

engine = create_async_engine(_url, **_engine_kwargs)

if settings.is_sqlite():

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _add_column(sync_conn, table: str, ddl: str) -> None:  # noqa: ANN001
    cols = {c["name"] for c in inspect(sync_conn).get_columns(table)}
    name = ddl.split()[0]
    if name not in cols:
        sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def migrate_schema(sync_conn) -> None:  # noqa: ANN001
    """SQLite has no Alembic yet — add missing columns/indexes on startup."""
    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())

    if "vacancies" in tables:
        cols = {c["name"] for c in inspector.get_columns("vacancies")}
        if "telegram_alias" not in cols:
            sync_conn.execute(text("ALTER TABLE vacancies ADD COLUMN telegram_alias VARCHAR(128)"))
        _add_column(sync_conn, "vacancies", "user_id INTEGER")
        _add_column(sync_conn, "vacancies", "telegram_message TEXT")
        _add_column(sync_conn, "vacancies", "fingerprint VARCHAR(190)")
        _add_column(sync_conn, "vacancies", "extra_sources JSON")
        _add_column(sync_conn, "vacancies", "duplicate_of_id INTEGER")
        _add_column(sync_conn, "vacancies", "last_touch_at DATETIME")
        _add_column(sync_conn, "vacancies", "stage_entered_at DATETIME")
        _add_column(sync_conn, "vacancies", "outreach_at DATETIME")
        _add_column(sync_conn, "vacancies", "pinged_at DATETIME")
        _add_column(sync_conn, "vacancies", "hh_pulse VARCHAR(32)")
        _add_column(sync_conn, "vacancies", "hh_pulse_at DATETIME")
        _add_column(sync_conn, "vacancies", "next_step_at DATETIME")
        _add_column(sync_conn, "vacancies", "next_step_kind VARCHAR(32)")
        _add_column(sync_conn, "vacancies", "google_event_id VARCHAR(128)")
        _add_column(sync_conn, "vacancies", "google_sync_error TEXT")
        _add_column(sync_conn, "vacancies", "contact_email VARCHAR(255)")
        _add_column(sync_conn, "vacancies", "contact_phone VARCHAR(64)")
        _add_column(sync_conn, "vacancies", "company_inn VARCHAR(16)")
        _add_column(sync_conn, "vacancies", "custom_values JSON")
        _add_column(sync_conn, "vacancies", "card_fields JSON")
        sync_conn.execute(
            text(
                """
                UPDATE vacancies
                SET stage_entered_at = COALESCE(
                    CASE WHEN pipeline_stage = 'waiting' THEN outreach_at END,
                    last_touch_at,
                    created_at
                )
                WHERE stage_entered_at IS NULL
                """
            )
        )
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vacancies_fingerprint ON vacancies (user_id, fingerprint)"))
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vacancies_duplicate_of_id ON vacancies (duplicate_of_id)"))
        inspector = inspect(sync_conn)
        for ix in inspector.get_indexes("vacancies"):
            cols = list(ix.get("column_names") or [])
            if ix.get("unique") and cols == ["source", "source_id"] and ix.get("name"):
                sync_conn.execute(text(f'DROP INDEX IF EXISTS "{ix["name"]}"'))
        for uq in inspector.get_unique_constraints("vacancies"):
            cols = list(uq.get("column_names") or [])
            if cols == ["source", "source_id"] and uq.get("name"):
                sync_conn.execute(text(f'DROP INDEX IF EXISTS "{uq["name"]}"'))
        sync_conn.execute(text("DROP INDEX IF EXISTS uq_vacancy_source_id"))
        sync_conn.execute(text("DROP INDEX IF EXISTS ix_vacancies_inbox"))
        sync_conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_vacancy_user_source_id "
                "ON vacancies (user_id, source, source_id)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vacancies_user_inbox "
                "ON vacancies (user_id, pipeline_stage, match_score)"
            )
        )

    if "scraper_configs" in tables:
        _add_column(sync_conn, "scraper_configs", "user_id INTEGER")
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scraper_configs_user_id ON scraper_configs (user_id)"))

    if "scraper_runs" in tables:
        _add_column(sync_conn, "scraper_runs", "user_id INTEGER")
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scraper_runs_user_id ON scraper_runs (user_id)"))

    if "user_profiles" in tables:
        _add_column(sync_conn, "user_profiles", "user_id INTEGER")
        _add_column(sync_conn, "user_profiles", "google_client_id TEXT")
        _add_column(sync_conn, "user_profiles", "google_client_secret TEXT")
        _add_column(sync_conn, "user_profiles", "google_refresh_token TEXT")
        _add_column(sync_conn, "user_profiles", "google_access_token TEXT")
        _add_column(sync_conn, "user_profiles", "google_token_expires_at DATETIME")
        _add_column(sync_conn, "user_profiles", "google_email VARCHAR(255)")
        _add_column(sync_conn, "user_profiles", "google_calendar_id VARCHAR(256)")
        _add_column(sync_conn, "user_profiles", "google_sync_token TEXT")
        _add_column(sync_conn, "user_profiles", "google_calendar_error TEXT")
        _add_column(sync_conn, "user_profiles", "google_pulled_at DATETIME")
        _add_column(sync_conn, "user_profiles", "custom_fields JSON")
        _add_column(sync_conn, "user_profiles", "active_hunt_id INTEGER")
        sync_conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profiles_user_id ON user_profiles (user_id)")
        )

    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    if "hunt_theses" in tables:
        _add_column(sync_conn, "hunt_theses", "custom_fields JSON")
        sync_conn.execute(
            text(
                """
                UPDATE hunt_theses
                SET custom_fields = (
                    SELECT custom_fields FROM user_profiles
                    WHERE user_profiles.user_id = hunt_theses.user_id
                      AND user_profiles.custom_fields IS NOT NULL
                      AND user_profiles.custom_fields NOT IN ('[]', 'null', '')
                )
                WHERE custom_fields IS NULL
                   OR custom_fields IN ('[]', 'null', '')
                """
            )
        )

    if "ping_slots" in tables:
        _add_column(sync_conn, "ping_slots", "synced_ping_at DATETIME")

    if "saved_contacts" in tables:
        _add_column(sync_conn, "saved_contacts", "company_inn VARCHAR(16)")

    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    if "vacancy_events" in tables:
        _add_column(sync_conn, "vacancy_events", "ends_at DATETIME")

    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    if "vacancies" in tables and "vacancy_events" in tables:
        sync_conn.execute(
            text(
                """
                INSERT INTO vacancy_events (
                    user_id, vacancy_id, kind, starts_at, ends_at, label,
                    google_event_id, google_sync_error, created_at, updated_at
                )
                SELECT
                    user_id,
                    id,
                    CASE
                        WHEN next_step_kind IN ('screening', 'interview', 'offer_deadline')
                        THEN next_step_kind
                        ELSE 'interview'
                    END,
                    next_step_at,
                    datetime(
                        next_step_at,
                        CASE WHEN next_step_kind = 'offer_deadline' THEN '+30 minutes' ELSE '+60 minutes' END
                    ),
                    NULL,
                    google_event_id,
                    google_sync_error,
                    datetime('now'),
                    datetime('now')
                FROM vacancies
                WHERE next_step_at IS NOT NULL
                  AND user_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM vacancy_events e WHERE e.vacancy_id = vacancies.id
                  )
                """
            )
        )
        sync_conn.execute(
            text(
                """
                UPDATE vacancy_events
                SET ends_at = datetime(
                    starts_at,
                    CASE WHEN kind = 'offer_deadline' THEN '+30 minutes' ELSE '+60 minutes' END
                )
                WHERE ends_at IS NULL AND starts_at IS NOT NULL
                """
            )
        )

    if "users" in tables:
        _add_column(sync_conn, "users", "is_host BOOLEAN DEFAULT 0 NOT NULL")
        _add_column(sync_conn, "users", "can_observe BOOLEAN DEFAULT 0 NOT NULL")
        has_host = sync_conn.execute(text("SELECT 1 FROM users WHERE is_host = 1 LIMIT 1")).fetchone()
        if has_host is None:
            first = sync_conn.execute(text("SELECT MIN(id) FROM users")).fetchone()
            if first and first[0] is not None:
                sync_conn.execute(text("UPDATE users SET is_host = 1 WHERE id = :id"), {"id": first[0]})
