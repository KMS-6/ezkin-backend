"""초기 사용자, My Shelf, 케어 루틴 스키마."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("nickname", sa.String(length=50), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_table(
        "care_contexts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("context_date", sa.Date(), nullable=False),
        sa.Column("care_mode", sa.String(length=30), nullable=False),
        sa.Column("observed_factors", sa.JSON(), nullable=False),
        sa.Column("ruleset_version", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_contexts")),
        sa.UniqueConstraint("user_id", "context_date", name=op.f("uq_care_contexts_user_id")),
    )
    op.create_index(op.f("ix_care_contexts_user_id"), "care_contexts", ["user_id"])
    op.create_table(
        "cosmetics",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("product_type", sa.String(length=30), nullable=False),
        sa.Column("ingredients_raw", sa.JSON(), nullable=True),
        sa.Column("image_key", sa.String(length=500), nullable=True),
        sa.Column("registration_source", sa.String(length=20), nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("user_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cosmetics")),
    )
    op.create_index(op.f("ix_cosmetics_deleted_at"), "cosmetics", ["deleted_at"])
    op.create_index(op.f("ix_cosmetics_user_id"), "cosmetics", ["user_id"])
    op.create_table(
        "care_routines",
        sa.Column("care_context_id", sa.Uuid(), nullable=False),
        sa.Column("time_of_day", sa.String(length=20), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=True),
        sa.Column("generation_source", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["care_context_id"], ["care_contexts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_routines")),
        sa.UniqueConstraint(
            "care_context_id", "time_of_day", name=op.f("uq_care_routines_care_context_id")
        ),
    )
    op.create_index(op.f("ix_care_routines_care_context_id"), "care_routines", ["care_context_id"])
    op.create_table(
        "routine_steps",
        sa.Column("routine_id", sa.Uuid(), nullable=False),
        sa.Column("cosmetic_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("amount_hint", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("caution_note", sa.Text(), nullable=True),
        sa.Column("product_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("step_order > 0", name=op.f("ck_routine_steps_positive_step_order")),
        sa.ForeignKeyConstraint(["cosmetic_id"], ["cosmetics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routine_id"], ["care_routines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_routine_steps")),
        sa.UniqueConstraint("routine_id", "step_order", name=op.f("uq_routine_steps_routine_id")),
    )
    op.create_index(op.f("ix_routine_steps_cosmetic_id"), "routine_steps", ["cosmetic_id"])
    op.create_index(op.f("ix_routine_steps_routine_id"), "routine_steps", ["routine_id"])


def downgrade() -> None:
    op.drop_table("routine_steps")
    op.drop_table("care_routines")
    op.drop_table("cosmetics")
    op.drop_table("care_contexts")
    op.drop_table("users")
