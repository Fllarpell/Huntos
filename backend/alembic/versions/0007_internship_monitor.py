"""Daily live status checks for internship catalog pages.

Revision ID: 0007_internship_monitor
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_internship_monitor"
down_revision = "0006_internship_tracks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internship_monitors",
        sa.Column("program_slug", sa.String(length=64), nullable=False),
        sa.Column("live_status", sa.String(length=16), nullable=False),
        sa.Column("signal", sa.String(length=255), nullable=True),
        sa.Column("check_error", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("program_slug"),
    )


def downgrade() -> None:
    op.drop_table("internship_monitors")
