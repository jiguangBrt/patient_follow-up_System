"""Doctor-wide student permissions with explicit view and optional expiry."""

import sqlalchemy as sa
from alembic import op

revision = "e94a61b2c705"
down_revision = "c83e2a17d604"
branch_labels = None
depends_on = None


def upgrade():
    # Keep prior patient-specific records intact. Saving the new settings
    # replaces their active effect and appends a doctor-wide history entry.
    with op.batch_alter_table("patient_grants") as batch:
        batch.drop_constraint("ck_patient_grant_dates", type_="check")
        batch.alter_column("patient_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column(
            "starts_at", existing_type=sa.DateTime(timezone=True), nullable=True
        )
        batch.alter_column(
            "ends_at", existing_type=sa.DateTime(timezone=True), nullable=True
        )
        batch.add_column(
            sa.Column("can_view", sa.Boolean(), server_default="1", nullable=False)
        )
        batch.create_check_constraint(
            "ck_patient_grant_dates",
            "(starts_at IS NULL AND ends_at IS NULL) OR (starts_at IS NOT NULL AND ends_at IS NOT NULL AND ends_at > starts_at)",
        )
        batch.create_check_constraint(
            "ck_patient_grant_view", "can_view OR (NOT can_edit AND NOT can_review)"
        )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM patient_grants WHERE patient_id IS NULL OR starts_at IS NULL OR ends_at IS NULL OR NOT can_view"
        )
    ):
        raise RuntimeError(
            "存在医生范围、永久或关闭查看的授权记录，不能自动降级丢失权限含义。"
        )
    with op.batch_alter_table("patient_grants") as batch:
        batch.drop_constraint("ck_patient_grant_dates", type_="check")
        batch.drop_constraint("ck_patient_grant_view", type_="check")
        batch.drop_column("can_view")
        batch.alter_column("patient_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column(
            "starts_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )
        batch.alter_column(
            "ends_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )
        batch.create_check_constraint("ck_patient_grant_dates", "ends_at > starts_at")
