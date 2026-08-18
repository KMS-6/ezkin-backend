"""Persona watch_status 컬럼 추가 (API 명세서 v0.4 Mock Persona 데이터 생성 규칙)."""

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_0009"
down_revision: str | None = "20260818_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "personas",
        sa.Column(
            "watch_status",
            sa.String(length=20),
            server_default="no_watch",
            nullable=False,
        ),
    )
    # persona_003(생리 주기·장기 사용 시나리오)은 워치 데이터 보유로 설정
    connection = op.get_bind()
    result = connection.execute(
        sa.text("UPDATE personas SET watch_status = 'has_watch' WHERE id = 'persona_003'")
    )
    if result.rowcount == 0:
        raise RuntimeError(
            "persona_003 not found — migration 20260818_0008 must run before this one"
        )


def downgrade() -> None:
    op.drop_column("personas", "watch_status")
