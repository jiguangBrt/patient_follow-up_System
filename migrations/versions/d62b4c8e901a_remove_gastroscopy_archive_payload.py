"""Remove the retired gastroscopy section from every archive version.

Revision ID: d62b4c8e901a
Revises: a91c4e8f602b

Only the top-level payload.gastroscopy key is removed. No record, source file,
other field, confirmation or account is deleted. Removed values cannot be
reconstructed by downgrade; recovery requires the pre-upgrade database backup.
"""
import warnings

import sqlalchemy as sa

from alembic import op

revision = "d62b4c8e901a"
down_revision = "a91c4e8f602b"
branch_labels = None
depends_on = None


def upgrade():
    records = sa.table(
        "gastritis_records",
        sa.column("id", sa.Integer),
        sa.column("payload", sa.JSON),
    )
    bind = op.get_bind()
    for row in bind.execute(sa.select(records.c.id, records.c.payload)).mappings():
        payload = row["payload"]
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid archive payload; cleanup stopped without guessing its contents.")
        if "gastroscopy" not in payload:
            continue
        cleaned = {key: value for key, value in payload.items() if key != "gastroscopy"}
        bind.execute(records.update().where(records.c.id == row["id"]).values(payload=cleaned))


def downgrade():
    # Reverting the revision cannot recreate deleted clinical values.
    warnings.warn(
        "Removed gastroscopy values cannot be restored by downgrade. "
        "Restore the pre-upgrade database backup if those values are required.",
        RuntimeWarning,
        stacklevel=2,
    )
