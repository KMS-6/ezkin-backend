"""SOS 챗봇 개인화 응답 필드(decision, used_contexts) 추가."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0003"
down_revision: str | None = "20260816_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sos_messages", sa.Column("decision", sa.JSON(), nullable=True))
    op.add_column("sos_messages", sa.Column("used_contexts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sos_messages", "used_contexts")
    op.drop_column("sos_messages", "decision")
