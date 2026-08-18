"""날씨 스냅샷 테이블 추가 — Briefing/위험도 6.1절 UV·습도 가중치용."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0004"
down_revision: str | None = "20260816_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weather_snapshots",
        sa.Column("persona_id", sa.String(length=30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("humidity_percent", sa.Float(), nullable=True),
        sa.Column("uv_index", sa.Float(), nullable=True),
        sa.Column("weather_condition", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["persona_id"],
            ["personas.id"],
            name=op.f("fk_weather_snapshots_persona_id_personas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weather_snapshots")),
    )
    op.create_index(
        op.f("ix_weather_snapshots_persona_id"), "weather_snapshots", ["persona_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_weather_snapshots_persona_id"), table_name="weather_snapshots")
    op.drop_table("weather_snapshots")
