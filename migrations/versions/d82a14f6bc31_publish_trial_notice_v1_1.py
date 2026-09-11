"""publish trial notice v1.1

Revision ID: d82a14f6bc31
Revises: c4e91d6a2f10
Create Date: 2026-09-11
"""

import hashlib
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d82a14f6bc31"
down_revision: Union[str, Sequence[str], None] = "c4e91d6a2f10"
branch_labels = None
depends_on = None


CONTENT = """这是患者随访系统的医生客户试用版患者须知。

当前试用用于验证建档、资料留存、医生审核和后续随访流程。试用阶段仅使用虚构或去标识化资料；系统尚未完成医院正式部署、实名身份认证以及临床、伦理、隐私和安全验收。

提交后，试用资料将由二维码创建医生查看和审核。系统会保留所见须知的版本、内容摘要、同意时间以及必要的试用入口信息。请勿填写真实姓名、手机号、证件号、病案号或真实临床信息。

如由家属或工作人员协助操作，应先取得患者授权。遇到真实医疗问题或紧急情况，请联系正规医疗机构或急救服务。"""


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    connection.execute(
        sa.text("""
            UPDATE patient_notice_versions
            SET status = 'retired', retired_at = :now, updated_at = :now
            WHERE notice_key = 'patient-intake-notice'
              AND version = '1.0.0' AND status = 'published'
        """),
        {"now": now},
    )
    connection.execute(
        sa.text("""
            INSERT INTO patient_notice_versions
                (notice_key, version, title, content, content_sha256, status,
                 published_at, effective_at, is_legacy_incomplete, created_at, updated_at)
            VALUES
                ('patient-intake-notice', '1.1.0', '患者须知与试用同意', :content,
                 :content_hash, 'published', :now, :now, 0, :now, :now)
        """),
        {"content": CONTENT, "content_hash": hashlib.sha256(CONTENT.encode()).hexdigest(), "now": now},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM patient_notice_versions WHERE notice_key = 'patient-intake-notice' AND version = '1.1.0'")
    )
    connection.execute(
        sa.text("""
            UPDATE patient_notice_versions
            SET status = 'published', retired_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE notice_key = 'patient-intake-notice' AND version = '1.0.0'
        """)
    )
