"""Per-user internship tracking.

Revision ID: 0006_internship_tracks
"""

import sqlalchemy as sa
from alembic import op

from app.db import Base
from app.models import *  # noqa: F401,F403

revision = "0006_internship_tracks"
down_revision = "0005_vacancy_searches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    op.drop_table("internship_tracks")
