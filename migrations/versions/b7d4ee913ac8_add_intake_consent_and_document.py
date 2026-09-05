"""add intake consent and document

Revision ID: b7d4ee913ac8
Revises: 942ac47e120e
Create Date: 2026-09-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b7d4ee913ac8"
down_revision: Union[str, Sequence[str], None] = "942ac47e120e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("patient_intake_submissions") as batch_op:
        batch_op.add_column(sa.Column("notice_version", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("document_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("document_mime_type", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("document_storage_name", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("document_sha256", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("extraction_status", sa.String(20), server_default="pending", nullable=False))
        batch_op.create_unique_constraint("uq_intake_document_storage_name", ["document_storage_name"])


def downgrade() -> None:
    with op.batch_alter_table("patient_intake_submissions") as batch_op:
        batch_op.drop_constraint("uq_intake_document_storage_name", type_="unique")
        for name in ("extraction_status", "document_sha256", "document_storage_name", "document_mime_type", "document_name", "consented_at", "notice_version"):
            batch_op.drop_column(name)
