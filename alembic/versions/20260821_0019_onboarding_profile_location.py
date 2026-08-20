"""onboarding_profile 위치 필드 추가

Revision ID: 20260821_0019
Revises: 20260821_0018
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0019"
down_revision: str | None = "20260821_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("onboarding_profiles", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("onboarding_profiles", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_profiles", "longitude")
    op.drop_column("onboarding_profiles", "latitude")
