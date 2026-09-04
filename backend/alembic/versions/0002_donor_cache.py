"""Host-side hh/HireHi listing cache.

Revision ID: 0002_donor_cache
"""

from alembic import op

from app.db import Base
from app.models import *  # noqa: F401,F403

revision = "0002_donor_cache"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    op.drop_table("donor_query_listings")
    op.drop_table("donor_listings")
    op.drop_table("donor_query_caches")
