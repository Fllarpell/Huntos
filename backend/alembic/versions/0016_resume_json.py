"""Structured resume JSON on the user profile.

Revision ID: 0016_resume_json
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_resume_json"
down_revision = "0015_chat_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("user_profiles")}
    if "resume_json" not in cols:
        op.add_column("user_profiles", sa.Column("resume_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("user_profiles")}
    if "resume_json" in cols:
        op.drop_column("user_profiles", "resume_json")
