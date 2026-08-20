"""personas.id를 참조하는 나머지 테이블의 persona_id 컬럼 폭을 VARCHAR(30)에서 넓힌다 —
20260821_0017에서 personas.id / generations.persona_id만 VARCHAR(36)으로 확장하고
나머지 테이블(briefings 등)을 누락해, 실사용자(UUID, 36자) persona_id로 INSERT 시
StringDataRightTruncationError가 발생하던 문제를 해결한다."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0021"
down_revision: str | None = "20260821_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_TO_36 = [
    "briefings",
    "consents",
    "daily_metrics",
    "generation_feedback",
    "notification_settings",
    "onboarding_profiles",
    "persona_cosmetics",
    "skin_scans",
    "sos_sessions",
    "sos_messages",
    "weather_snapshots",
]


def upgrade() -> None:
    for table in TABLES_TO_36:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "persona_id",
                type_=sa.String(36),
                existing_type=sa.String(30),
            )
    with op.batch_alter_table("reports") as batch_op:
        batch_op.alter_column(
            "persona_id",
            type_=sa.String(100),
            existing_type=sa.String(30),
        )


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.alter_column(
            "persona_id",
            type_=sa.String(30),
            existing_type=sa.String(100),
        )
    for table in reversed(TABLES_TO_36):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "persona_id",
                type_=sa.String(30),
                existing_type=sa.String(36),
            )
