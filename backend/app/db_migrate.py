"""Schema bootstrap: sqlite ALTER path vs Alembic on Postgres."""

from __future__ import annotations

import asyncio

from app.config import BACKEND_DIR, settings


def _alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    url = settings.database_migrate_url or settings.database_url
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


async def apply_schema() -> None:
    from app.db import Base, engine, migrate_schema

    if settings.is_sqlite():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(migrate_schema)
        return
    await asyncio.to_thread(_alembic_upgrade)
