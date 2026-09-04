"""Optional name and reply-to on feedback notes.

Revision ID: 0013_feedback_meta
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_feedback_meta"
down_revision = "0012_telegram_bot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feedback_notes", sa.Column("contact_name", sa.String(length=128), nullable=True))
    op.add_column("feedback_notes", sa.Column("reply_to", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("feedback_notes", "reply_to")
    op.drop_column("feedback_notes", "contact_name")
