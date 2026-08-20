"""personas.id / generations.persona_id 컬럼 폭을 VARCHAR(30)에서 VARCHAR(36)으로 확장 —
실사용자(액세스 토큰 인증)는 str(User.id)(UUID, 36자)를 persona_id로 사용해 기존
persona_id 기반 도메인 로직에 편입시키기 위함 (app/core/mock_persona.py 참고)."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0017"
down_revision: str | None = "20260821_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("personas") as batch_op:
        batch_op.alter_column(
            "id",
            type_=sa.String(36),
            existing_type=sa.String(30),
        )
    with op.batch_alter_table("generations") as batch_op:
        batch_op.alter_column(
            "persona_id",
            type_=sa.String(36),
            existing_type=sa.String(30),
        )


def downgrade() -> None:
    with op.batch_alter_table("generations") as batch_op:
        batch_op.alter_column(
            "persona_id",
            type_=sa.String(30),
            existing_type=sa.String(36),
        )
    with op.batch_alter_table("personas") as batch_op:
        batch_op.alter_column(
            "id",
            type_=sa.String(30),
            existing_type=sa.String(36),
        )
