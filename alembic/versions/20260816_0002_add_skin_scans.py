"""SkinScan 테이블 추가.

Revision ID: 20260816_0002
Revises: 20260814_0001
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skin_scans",
        sa.Column("persona_id", sa.String(length=60), nullable=False),
        sa.Column("capture_method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lower_accuracy", sa.Boolean(), nullable=False),
        sa.Column("image_key", sa.String(length=500), nullable=True),
        sa.Column("questionnaire_answers", sa.JSON(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column("failure", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("idempotency_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skin_scans")),
        sa.UniqueConstraint("persona_id", "idempotency_key", name=op.f("uq_skin_scans_persona_id")),
    )
    op.create_index(op.f("ix_skin_scans_idempotency_key"), "skin_scans", ["idempotency_key"])
    op.create_index(op.f("ix_skin_scans_persona_id"), "skin_scans", ["persona_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_skin_scans_persona_id"), table_name="skin_scans")
    op.drop_index(op.f("ix_skin_scans_idempotency_key"), table_name="skin_scans")
    op.drop_table("skin_scans")
