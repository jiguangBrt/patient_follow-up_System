"""Remove obsolete authorization history; retain only current settings."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "f05b31d6a902"
down_revision = "e94a61b2c705"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    connection.execute(
        sa.text(
            "DELETE FROM patient_grants WHERE revoked_at IS NOT NULL OR (ends_at IS NOT NULL AND ends_at <= :now)"
        ),
        {"now": now},
    )
    # Normal writes already have only one current doctor-wide setting.
    # Remove any duplicate superseded doctor-wide rows without broadening scope.
    connection.execute(
        sa.text(
            "DELETE FROM patient_grants AS old WHERE old.patient_id IS NULL AND EXISTS (SELECT 1 FROM patient_grants AS newer WHERE newer.student_id=old.student_id AND newer.granted_by_id=old.granted_by_id AND newer.patient_id IS NULL AND newer.id>old.id)"
        )
    )
    with op.batch_alter_table("patient_grants") as batch:
        batch.drop_column("revoked_by_id")
        batch.drop_column("revoked_at")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM patient_grants")):
        raise RuntimeError(
            "存在当前权限配置；已清理的历史不能通过降级重建，请先评估备份与迁移。"
        )
    with op.batch_alter_table("patient_grants") as batch:
        batch.add_column(
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("revoked_by_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_patient_grants_revoked_by_id_users", "users", ["revoked_by_id"], ["id"]
        )
