"""Persist the Vision analysis model and schema metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0010"
down_revision: str | None = "20260818_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("skin_scans", sa.Column("analysis_provider", sa.String(50), nullable=True))
    op.add_column("skin_scans", sa.Column("analysis_model", sa.String(100), nullable=True))
    op.add_column("skin_scans", sa.Column("analysis_model_version", sa.String(50), nullable=True))
    op.add_column("skin_scans", sa.Column("analysis_schema_version", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("skin_scans", "analysis_schema_version")
    op.drop_column("skin_scans", "analysis_model_version")
    op.drop_column("skin_scans", "analysis_model")
    op.drop_column("skin_scans", "analysis_provider")
