"""Hackathon event tables.

Revision ID: 0008_hackathons
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_hackathons"
down_revision = "0007_internship_monitor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hackathon_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("registration_status", sa.String(length=16), nullable=False),
        sa.Column("event_status", sa.String(length=16), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.String(length=512), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("check_error", sa.Text(), nullable=True),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_id", name="uq_hackathon_source_id"),
    )
    op.create_index("ix_hackathon_events_source", "hackathon_events", ["source"])

    op.create_table(
        "hackathon_tracks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("track_status", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["hackathon_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_hackathon_track_user_event"),
    )
    op.create_index("ix_hackathon_tracks_user_id", "hackathon_tracks", ["user_id"])
    op.create_index("ix_hackathon_tracks_event_id", "hackathon_tracks", ["event_id"])


def downgrade() -> None:
    op.drop_table("hackathon_tracks")
    op.drop_table("hackathon_events")
