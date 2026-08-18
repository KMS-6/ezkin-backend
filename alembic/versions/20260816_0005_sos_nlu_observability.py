"""SOS 챗봇 파싱 관측 필드(intent, parse_confidence) 추가 — 18.1/18.3절."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0005"
down_revision: str | None = "20260816_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sos_messages", sa.Column("intent", sa.String(length=30), nullable=True))
    op.add_column("sos_messages", sa.Column("parse_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("sos_messages", "parse_confidence")
    op.drop_column("sos_messages", "intent")
