"""In-app bug reports and ideas.

Revision ID: 0011_feedback
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_feedback"
down_revision = "0010_google_sub"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("page", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_feedback_notes_user_id", "feedback_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_notes_user_id", table_name="feedback_notes")
    op.drop_table("feedback_notes")
