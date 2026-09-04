"""Exclude companies from a hunt thesis.

Revision ID: 0004_exclude_companies
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.db import Base
from app.models import *  # noqa: F401,F403

revision = "0004_exclude_companies"
down_revision = "0003_scrape_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    if "hunt_theses" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("hunt_theses")}
        if "exclude_companies" not in cols:
            op.add_column("hunt_theses", sa.Column("exclude_companies", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("hunt_theses", "exclude_companies")
