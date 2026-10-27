"""Add students owned by doctors and dated patient authorization history."""

from alembic import op
import sqlalchemy as sa

revision = "c83e2a17d604"
down_revision = "b72d9015f43a"
branch_labels = None
depends_on = None


def upgrade():
    # Existing SQLite role is VARCHAR(7), already wide enough for 'student'.
    # A nullable self-reference preserves every existing account and role.
    op.execute(
        "ALTER TABLE users ADD COLUMN mentor_doctor_id INTEGER REFERENCES users(id)"
    )
    op.create_index("ix_users_mentor_doctor_id", "users", ["mentor_doctor_id"])
    op.create_table(
        "patient_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False
        ),
        sa.Column(
            "student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "granted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("purpose", sa.String(300), nullable=False),
        sa.Column("can_edit", sa.Boolean(), nullable=False),
        sa.Column("can_review", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_patient_grant_dates"),
    )
    for column in ("patient_id", "student_id", "granted_by_id"):
        op.create_index(f"ix_patient_grants_{column}", "patient_grants", [column])


def downgrade():
    # Do not silently turn students into doctors/patients or lose authorization history.
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT count(*) FROM users WHERE role = 'student'")
    ) or connection.scalar(sa.text("SELECT count(*) FROM patient_grants")):
        raise RuntimeError(
            "存在学生账号或授权历史，不能自动降级；请保留备份并人工迁移后重试。"
        )
    op.drop_table("patient_grants")
    op.drop_index("ix_users_mentor_doctor_id", table_name="users")
    op.drop_column("users", "mentor_doctor_id")
