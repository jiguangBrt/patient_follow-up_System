"""make intake submission account optional

Revision ID: 942ac47e120e
Revises: 6a7ce45fb102
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "942ac47e120e"
down_revision: Union[str, Sequence[str], None] = "6a7ce45fb102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("patient_intake_submissions") as batch_op:
        batch_op.drop_constraint("uq_intake_link_patient_user", type_="unique")
        batch_op.alter_column("submitted_by_user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("submission_digest", sa.String(length=64), nullable=True))
        batch_op.alter_column("submission_digest", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_index("ix_patient_intake_submissions_submission_digest", ["submission_digest"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("patient_intake_submissions") as batch_op:
        batch_op.drop_index("ix_patient_intake_submissions_submission_digest")
        batch_op.drop_column("submission_digest")
        batch_op.alter_column("submitted_by_user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint("uq_intake_link_patient_user", ["intake_link_id", "submitted_by_user_id"])
