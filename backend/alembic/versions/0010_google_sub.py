"""Google account id for Sign-In.

Revision ID: 0010_google_sub
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_google_sub"
down_revision = "0009_hackathon_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
