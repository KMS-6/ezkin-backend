"""Pin claim versions in knowledge indexes."""

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0010"
down_revision: str | None = "20260818_0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_indexes",
        sa.Column(
            "claim_versions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_indexes", "claim_versions")
