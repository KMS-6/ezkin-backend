"""SOS 챗봇 LLM escalation 여부 기록(llm_escalated) 추가 — 10.2절 4단계, 18.3절."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0006"
down_revision: str | None = "20260816_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sos_messages",
        sa.Column("llm_escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("sos_messages", "llm_escalated")
