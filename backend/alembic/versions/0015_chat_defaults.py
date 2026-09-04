"""Server defaults for conversation timestamps.

Revision ID: 0015_chat_defaults
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_chat_defaults"
down_revision = "0014_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "conversations",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "conversations",
        "updated_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "conversations",
        "updated_at",
        existing_type=sa.DateTime(),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "conversations",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=None,
        existing_nullable=False,
    )
