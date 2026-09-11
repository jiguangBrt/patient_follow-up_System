"""create patient documents and review timeline

Revision ID: e51bc83f6a20
Revises: d82a14f6bc31
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e51bc83f6a20"
down_revision: Union[str, Sequence[str], None] = "d82a14f6bc31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("notice_version_id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("display_label", sa.String(length=100), nullable=False),
        sa.Column("patient_note", sa.String(length=500), nullable=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("storage_name", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("notice_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_status", sa.String(length=20), server_default="not_run", nullable=False),
        sa.Column("review_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("confirmed_event_date", sa.Date(), nullable=True),
        sa.Column("confirmed_label", sa.String(length=100), nullable=True),
        sa.Column("doctor_summary", sa.String(length=1000), nullable=True),
        sa.Column("reviewed_by_doctor_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("extraction_status IN ('pending', 'not_run')", name="ck_patient_document_extraction_status"),
        sa.CheckConstraint("review_status IN ('pending', 'approved', 'rejected')", name="ck_patient_document_review_status"),
        sa.CheckConstraint("size_bytes > 0", name="ck_patient_document_size_positive"),
        sa.ForeignKeyConstraint(["notice_version_id"], ["patient_notice_versions.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_doctor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_index(op.f("ix_patient_documents_patient_id"), "patient_documents", ["patient_id"])
    op.create_index(op.f("ix_patient_documents_submitted_by_user_id"), "patient_documents", ["submitted_by_user_id"])
    op.create_index(op.f("ix_patient_documents_notice_version_id"), "patient_documents", ["notice_version_id"])
    op.create_index(op.f("ix_patient_documents_event_date"), "patient_documents", ["event_date"])
    op.create_index(op.f("ix_patient_documents_review_status"), "patient_documents", ["review_status"])
    op.create_index(op.f("ix_patient_documents_confirmed_event_date"), "patient_documents", ["confirmed_event_date"])
    op.create_index(op.f("ix_patient_documents_reviewed_by_doctor_id"), "patient_documents", ["reviewed_by_doctor_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_patient_documents_reviewed_by_doctor_id"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_confirmed_event_date"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_review_status"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_event_date"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_notice_version_id"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_submitted_by_user_id"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_patient_id"), table_name="patient_documents")
    op.drop_table("patient_documents")
