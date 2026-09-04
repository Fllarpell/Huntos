"""Vacancy search provenance + stack_ids.

Revision ID: 0005_vacancy_searches
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

from app.db import Base
from app.models import *  # noqa: F401,F403

revision = "0005_vacancy_searches"
down_revision = "0004_exclude_companies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    if "vacancies" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("vacancies")}
        if "stack_ids" not in cols:
            op.add_column("vacancies", sa.Column("stack_ids", sa.JSON(), nullable=True))
    if "vacancy_searches" in inspector.get_table_names():
        bind.execute(
            text(
                """
                INSERT INTO vacancy_searches (vacancy_id, scraper_config_id)
                SELECT id, scraper_config_id FROM vacancies
                WHERE scraper_config_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """
            )
        )


def downgrade() -> None:
    op.drop_table("vacancy_searches")
    op.drop_column("vacancies", "stack_ids")
