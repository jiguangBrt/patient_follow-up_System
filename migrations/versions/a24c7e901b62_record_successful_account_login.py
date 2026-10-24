"""Record the most recent successful account login in UTC."""

from alembic import op
import sqlalchemy as sa

revision = "a24c7e901b62"
down_revision = "f21a8b43c190"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("users", "last_login_at")
