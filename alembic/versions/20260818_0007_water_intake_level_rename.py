"""daily_metrics.hydration_level 컬럼을 water_intake_level로 이름 변경 — API명세서.md
`/daily-metrics/manual` 필드명·enum 정합성 맞춤."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260818_0007"
down_revision: str | None = "20260816_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "daily_metrics",
        "hydration_level",
        new_column_name="water_intake_level",
    )


def downgrade() -> None:
    op.alter_column(
        "daily_metrics",
        "water_intake_level",
        new_column_name="hydration_level",
    )
