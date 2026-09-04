"""Direct chat threads and user last_seen.

Revision ID: 0014_chat
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_chat"
down_revision = "0013_feedback_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dm_key", sa.String(length=64), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_conversations_dm_key", "conversations", ["dm_key"], unique=True)
    op.create_table(
        "conversation_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),
    )
    op.create_index("ix_conversation_members_conversation_id", "conversation_members", ["conversation_id"])
    op.create_index("ix_conversation_members_user_id", "conversation_members", ["user_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_conversation_members_user_id", table_name="conversation_members")
    op.drop_index("ix_conversation_members_conversation_id", table_name="conversation_members")
    op.drop_table("conversation_members")
    op.drop_index("ix_conversations_dm_key", table_name="conversations")
    op.drop_table("conversations")
    op.drop_column("users", "last_seen_at")
