"""Shared donor cache queue + query_key on scraper_configs.

Revision ID: 0003_scrape_queue
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.db import Base
from app.models import *  # noqa: F401,F403

revision = "0003_scrape_queue"
down_revision = "0002_donor_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    if "scraper_configs" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("scraper_configs")}
        if "query_key" not in cols:
            op.add_column("scraper_configs", sa.Column("query_key", sa.String(length=64), nullable=True))
        indexes = {ix["name"] for ix in inspector.get_indexes("scraper_configs")}
        if "ix_scraper_configs_query_key" not in indexes:
            op.create_index("ix_scraper_configs_query_key", "scraper_configs", ["query_key"])


def downgrade() -> None:
    op.drop_index("ix_scraper_configs_query_key", table_name="scraper_configs")
    op.drop_column("scraper_configs", "query_key")
    op.drop_table("scrape_queue")
