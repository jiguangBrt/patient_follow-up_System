"""version patient notice and demo consent

Revision ID: c4e91d6a2f10
Revises: b7d4ee913ac8
Create Date: 2026-09-11
"""

import hashlib
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e91d6a2f10"
down_revision: Union[str, Sequence[str], None] = "b7d4ee913ac8"
branch_labels = None
depends_on = None


CURRENT_CONTENT = """这是患者随访系统作品集的内部演示须知。

本演示仅使用虚构或去标识化资料，用于展示建档、资料留存和医生审核流程。它不是医院正式系统，不提供诊断、处方、急救、正式医疗身份认证或具有法律效力的电子签名。

提交后，演示资料将由二维码创建医生查看和审核。系统会保留所见须知的版本、内容摘要、同意时间以及必要的演示入口信息。请勿填写真实姓名、手机号、证件号、病案号或真实临床信息。

如由家属或工作人员协助操作，应先取得患者授权。遇到真实医疗问题或紧急情况，请联系正规医疗机构或急救服务。"""

LEGACY_CONTENT = "历史演示记录仅保存了 demo-notice-v1 标识和同意时间，无法证明当时展示的完整正文。"


def upgrade() -> None:
    op.create_table(
        "patient_notice_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notice_key", sa.String(80), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
        sa.Column("is_legacy_incomplete", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_patient_notice_status"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notice_key", "version", name="uq_patient_notice_key_version"),
    )
    op.create_index("ix_patient_notice_versions_notice_key", "patient_notice_versions", ["notice_key"])
    op.create_index("ix_patient_notice_versions_status", "patient_notice_versions", ["status"])
    op.create_index(
        "uq_patient_notice_one_published",
        "patient_notice_versions",
        ["notice_key"],
        unique=True,
        sqlite_where=sa.text("status = 'published' AND retired_at IS NULL"),
    )
    op.create_table(
        "patient_demo_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notice_version_id", sa.Integer(), nullable=False),
        sa.Column("intake_submission_id", sa.Integer(), nullable=False),
        sa.Column("patient_user_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.String(50), nullable=False),
        sa.Column("notice_content_sha256", sa.String(64), nullable=False),
        sa.Column("is_legacy_incomplete", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["intake_submission_id"], ["patient_intake_submissions.id"]),
        sa.ForeignKeyConstraint(["notice_version_id"], ["patient_notice_versions.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("intake_submission_id", "notice_version_id", name="uq_intake_notice_consent"),
    )
    for column in ("notice_version_id", "intake_submission_id", "patient_user_id", "patient_id"):
        op.create_index(f"ix_patient_demo_consents_{column}", "patient_demo_consents", [column])

    connection = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    notice_table = sa.table(
        "patient_notice_versions",
        sa.column("id", sa.Integer()), sa.column("notice_key", sa.String()),
        sa.column("version", sa.String()), sa.column("title", sa.String()),
        sa.column("content", sa.Text()), sa.column("content_sha256", sa.String()),
        sa.column("status", sa.String()), sa.column("published_at", sa.DateTime()),
        sa.column("effective_at", sa.DateTime()), sa.column("retired_at", sa.DateTime()),
        sa.column("is_legacy_incomplete", sa.Boolean()),
    )
    connection.execute(notice_table.insert(), {
        "id": 1, "notice_key": "patient-intake-notice", "version": "demo-notice-v1-legacy",
        "title": "历史演示患者须知记录", "content": LEGACY_CONTENT,
        "content_sha256": hashlib.sha256(LEGACY_CONTENT.encode()).hexdigest(),
        "status": "retired", "is_legacy_incomplete": True,
    })
    connection.execute(notice_table.insert(), {
        "id": 2, "notice_key": "patient-intake-notice", "version": "1.0.0",
        "title": "患者须知与演示同意", "content": CURRENT_CONTENT,
        "content_sha256": hashlib.sha256(CURRENT_CONTENT.encode()).hexdigest(),
        "status": "published", "published_at": now, "effective_at": now,
        "is_legacy_incomplete": False,
    })
    legacy_hash = hashlib.sha256(LEGACY_CONTENT.encode()).hexdigest()
    connection.execute(sa.text("""
        INSERT INTO patient_demo_consents
            (notice_version_id, intake_submission_id, patient_user_id, patient_id,
             consented_at, context, notice_content_sha256, is_legacy_incomplete)
        SELECT 1, id, submitted_by_user_id, created_patient_id, consented_at,
               'legacy-intake-record', :legacy_hash, 1
        FROM patient_intake_submissions
        WHERE notice_version = 'demo-notice-v1' AND consented_at IS NOT NULL
    """), {"legacy_hash": legacy_hash})


def downgrade() -> None:
    for column in ("patient_id", "patient_user_id", "intake_submission_id", "notice_version_id"):
        op.drop_index(f"ix_patient_demo_consents_{column}", table_name="patient_demo_consents")
    op.drop_table("patient_demo_consents")
    op.drop_index("uq_patient_notice_one_published", table_name="patient_notice_versions")
    op.drop_index("ix_patient_notice_versions_status", table_name="patient_notice_versions")
    op.drop_index("ix_patient_notice_versions_notice_key", table_name="patient_notice_versions")
    op.drop_table("patient_notice_versions")
