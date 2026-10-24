"""Keep the doctor-confirmed date used for patient visit grouping."""

from alembic import op
import sqlalchemy as sa

revision = "b72d9015f43a"
down_revision = "a24c7e901b62"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "clinical_documents", sa.Column("visit_date", sa.Date(), nullable=True)
    )


def downgrade():
    op.drop_column("clinical_documents", "visit_date")
