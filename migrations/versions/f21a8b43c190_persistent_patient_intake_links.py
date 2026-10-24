"""Persistent patient-specific QR links, and repeated patient submissions."""

from alembic import op
import sqlalchemy as sa

revision = "f21a8b43c190"
down_revision = "055c532be7e7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("patient_intake_links") as batch:
        batch.add_column(sa.Column("patient_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("access_nonce", sa.String(64), nullable=True))
        batch.create_foreign_key(
            "fk_intake_link_patient", "patients", ["patient_id"], ["id"]
        )
        batch.create_unique_constraint("uq_intake_link_patient", ["patient_id"])
    with op.batch_alter_table(
        "patient_intake_submissions",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch:
        batch.drop_constraint(
            "uq_patient_intake_submissions_created_patient_id", type_="unique"
        )


def downgrade():
    # Refuse to discard repeated submissions to satisfy the old uniqueness rule.
    with op.batch_alter_table("patient_intake_submissions") as batch:
        batch.create_unique_constraint(
            "uq_patient_intake_submissions_created_patient_id", ["created_patient_id"]
        )
    with op.batch_alter_table("patient_intake_links") as batch:
        batch.drop_constraint("uq_intake_link_patient", type_="unique")
        batch.drop_constraint("fk_intake_link_patient", type_="foreignkey")
        batch.drop_column("access_nonce")
        batch.drop_column("patient_id")
