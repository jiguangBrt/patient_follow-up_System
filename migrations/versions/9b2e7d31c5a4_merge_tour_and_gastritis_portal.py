"""Merge onboarding tour and gastritis portal migration branches."""

from alembic import op
import sqlalchemy as sa

revision = "9b2e7d31c5a4"
down_revision = ("c31f9a2e8d04", "e73c5d9f012b")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
