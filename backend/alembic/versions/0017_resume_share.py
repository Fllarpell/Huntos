"""Opt-in public resume share token.

Revision ID: 0017_resume_share
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_resume_share"
down_revision = "0016_resume_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("user_profiles")}
    if "resume_public" not in cols:
        op.add_column(
            "user_profiles",
            sa.Column("resume_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "resume_share_id" not in cols:
        op.add_column("user_profiles", sa.Column("resume_share_id", sa.String(length=32), nullable=True))
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("user_profiles")}
    if "uq_user_profiles_resume_share_id" not in indexes:
        op.create_index(
            "uq_user_profiles_resume_share_id",
            "user_profiles",
            ["resume_share_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("user_profiles")}
    if "uq_user_profiles_resume_share_id" in indexes:
        op.drop_index("uq_user_profiles_resume_share_id", table_name="user_profiles")
    cols = {c["name"] for c in sa.inspect(bind).get_columns("user_profiles")}
    if "resume_share_id" in cols:
        op.drop_column("user_profiles", "resume_share_id")
    if "resume_public" in cols:
        op.drop_column("user_profiles", "resume_public")
