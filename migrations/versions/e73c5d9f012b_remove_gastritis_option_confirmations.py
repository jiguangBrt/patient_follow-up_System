"""Remove the retired questionnaire confirmation workflow and its stored data.

Revision ID: e73c5d9f012b
Revises: d62b4c8e901a

Dropping this table permanently removes its records. Downgrade creates only an
empty compatible table; restoring historical values requires a prior backup.
Clinical archive records and their actual clinical review provenance are kept.
"""
import warnings

import sqlalchemy as sa

from alembic import op

revision = "e73c5d9f012b"
down_revision = "d62b4c8e901a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_gastritis_option_confirmations_doctor_id", table_name="gastritis_option_confirmations")
    op.drop_table("gastritis_option_confirmations")


def downgrade():
    warnings.warn(
        "Retired questionnaire confirmation values cannot be restored by downgrade. "
        "Only an empty table is recreated; restore a prior backup for historical values.",
        RuntimeWarning,
        stacklevel=2,
    )
    op.create_table(
        "gastritis_option_confirmations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gastritis_option_confirmations_doctor_id", "gastritis_option_confirmations", ["doctor_id"], unique=False)
