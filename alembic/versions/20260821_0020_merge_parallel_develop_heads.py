"""develop 병렬 마이그레이션 head 통합 (0010/0019)

Revision ID: 20260821_0020
Revises: 20260820_0010, 20260821_0019
Create Date: 2026-08-21 08:24:12.591284
"""

from collections.abc import Sequence

revision: str = "20260821_0020"
down_revision: str | tuple[str, ...] | None = ("20260820_0010", "20260821_0019")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
