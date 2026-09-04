"""Per-user Telegram bot bind and notices.

Revision ID: 0012_telegram_bot
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_telegram_bot"
down_revision = "0011_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_bot_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_token", sa.Text(), nullable=True),
        sa.Column("bot_username", sa.String(length=64), nullable=True),
        sa.Column("update_offset", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "telegram_bot_binds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("want_vacancies", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("want_internships", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("want_hackathons", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("want_steps", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("want_ping", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cursor_at", sa.DateTime(), nullable=True),
        sa.Column("last_digest_on", sa.String(length=10), nullable=True),
        sa.Column("open_internship_slugs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_telegram_bot_binds_user_id", "telegram_bot_binds", ["user_id"], unique=True)
    op.create_index("ix_telegram_bot_binds_telegram_user_id", "telegram_bot_binds", ["telegram_user_id"], unique=True)
    op.create_table(
        "telegram_link_tokens",
        sa.Column("token", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"])
    op.create_table(
        "telegram_notices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("subject_key", sa.String(length=128), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "kind", "subject_key", name="uq_telegram_notice"),
    )
    op.create_index("ix_telegram_notices_user_id", "telegram_notices", ["user_id"])


def downgrade() -> None:
    op.drop_table("telegram_notices")
    op.drop_table("telegram_link_tokens")
    op.drop_table("telegram_bot_binds")
    op.drop_table("telegram_bot_state")
