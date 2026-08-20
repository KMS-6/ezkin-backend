"""knowledge_chunks.created_at/updated_at server_default를 Postgres 전용 now()에서
CURRENT_TIMESTAMP로 교정 — SQLite 마이그레이션 테스트(test_migrations.py)에서도
동작하도록 표준 SQL 함수로 통일한다. 20260816_0002_knowledge_tables.py는 이미
main/develop에 병합돼 직접 수정하지 않고 새 마이그레이션으로 교정한다."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0015"
down_revision: str | None = "20260821_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        )
