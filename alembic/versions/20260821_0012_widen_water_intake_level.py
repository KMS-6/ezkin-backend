"""daily_metrics.water_intake_level 컬럼 폭을 VARCHAR(20)에서 VARCHAR(30)으로 확장 —
enum 값 "three_to_five_glasses"(21자)가 기존 폭을 초과해 Postgres INSERT가
StringDataRightTruncationError로 실패하던 기존 버그 수정."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0012"
down_revision: str | None = "20260821_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("daily_metrics") as batch_op:
        batch_op.alter_column(
            "water_intake_level",
            type_=sa.String(30),
            existing_type=sa.String(20),
        )


def downgrade() -> None:
    with op.batch_alter_table("daily_metrics") as batch_op:
        batch_op.alter_column(
            "water_intake_level",
            type_=sa.String(20),
            existing_type=sa.String(30),
        )
