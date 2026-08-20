"""skin_scans에 idempotency_key, idempotency_payload_hash 컬럼 추가 — 모델 변경이 누락된 컬럼."""

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0011"
down_revision: str | None = "20260821_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skin_scans", sa.Column("idempotency_key", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "skin_scans",
        sa.Column("idempotency_payload_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_skin_scans_idempotency_key"),
        "skin_scans",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_skin_scans_idempotency_key"), table_name="skin_scans")
    op.drop_column("skin_scans", "idempotency_payload_hash")
    op.drop_column("skin_scans", "idempotency_key")
