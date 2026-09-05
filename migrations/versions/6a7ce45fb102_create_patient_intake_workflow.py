"""create patient intake workflow

Revision ID: 6a7ce45fb102
Revises: 14d35a334950
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a7ce45fb102"
down_revision: Union[str, Sequence[str], None] = "14d35a334950"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_intake_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_by_doctor_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_submissions", sa.Integer(), server_default="100", nullable=False),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("max_submissions > 0", name="ck_intake_link_max_positive"),
        sa.CheckConstraint("used_count >= 0", name="ck_intake_link_used_nonnegative"),
        sa.CheckConstraint("used_count <= max_submissions", name="ck_intake_link_within_limit"),
        sa.ForeignKeyConstraint(["created_by_doctor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_intake_links_token_digest", "patient_intake_links", ["token_digest"], unique=True)
    op.create_index("ix_patient_intake_links_created_by_doctor_id", "patient_intake_links", ["created_by_doctor_id"])
    op.create_table(
        "patient_intake_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("intake_link_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("sex", sa.String(length=20), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("operator_relationship", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("reviewed_by_doctor_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("created_patient_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["intake_link_id"], ["patient_intake_links.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_doctor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("created_patient_id"),
        sa.UniqueConstraint("intake_link_id", "submitted_by_user_id", name="uq_intake_link_patient_user"),
    )
    op.create_index("ix_patient_intake_submissions_intake_link_id", "patient_intake_submissions", ["intake_link_id"])
    op.create_index("ix_patient_intake_submissions_submitted_by_user_id", "patient_intake_submissions", ["submitted_by_user_id"])
    op.create_index("ix_patient_intake_submissions_status", "patient_intake_submissions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_patient_intake_submissions_status", table_name="patient_intake_submissions")
    op.drop_index("ix_patient_intake_submissions_submitted_by_user_id", table_name="patient_intake_submissions")
    op.drop_index("ix_patient_intake_submissions_intake_link_id", table_name="patient_intake_submissions")
    op.drop_table("patient_intake_submissions")
    op.drop_index("ix_patient_intake_links_created_by_doctor_id", table_name="patient_intake_links")
    op.drop_index("ix_patient_intake_links_token_digest", table_name="patient_intake_links")
    op.drop_table("patient_intake_links")
