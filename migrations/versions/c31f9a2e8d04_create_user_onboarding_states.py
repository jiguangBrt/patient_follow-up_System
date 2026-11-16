"""Create per-account onboarding tour states."""

from alembic import op
import sqlalchemy as sa

revision = "c31f9a2e8d04"
down_revision = "f05b31d6a902"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_onboarding_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tour_key", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "tour_key", name="uq_onboarding_user_tour"),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'skipped')",
            name="ck_onboarding_status",
        ),
    )
    op.create_index(
        "ix_user_onboarding_states_user_id",
        "user_onboarding_states",
        ["user_id"],
    )


def downgrade():
    op.drop_index(
        "ix_user_onboarding_states_user_id", table_name="user_onboarding_states"
    )
    op.drop_table("user_onboarding_states")
