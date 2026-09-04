"""Hackathon prize, organizer, image.

Revision ID: 0009_hackathon_meta
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_hackathon_meta"
down_revision = "0008_hackathons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hackathon_events", sa.Column("prize_text", sa.String(length=128), nullable=True))
    op.add_column("hackathon_events", sa.Column("organizer", sa.String(length=255), nullable=True))
    op.add_column("hackathon_events", sa.Column("image_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("hackathon_events", "image_url")
    op.drop_column("hackathon_events", "organizer")
    op.drop_column("hackathon_events", "prize_text")
