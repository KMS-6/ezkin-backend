"""daily_metrics.water_intake_level을 API enum 길이에 맞게 확장."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0010"
down_revision: str | None = "20260818_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("daily_metrics") as batch_op:
        batch_op.alter_column(
            "water_intake_level",
            existing_type=sa.String(length=20),
            type_=sa.String(length=32),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("daily_metrics") as batch_op:
        batch_op.alter_column(
            "water_intake_level",
            existing_type=sa.String(length=32),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
