"""cosmetics → user_cosmetics 테이블 rename, skin_scans 컬럼 ERD 정렬, skin_questionnaire_answers 신설.

Revision ID: 20260818_0003
Revises: 20260816_0002
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_0003"
down_revision: str | None = "20260816_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. cosmetics → user_cosmetics (PostgreSQL이 FK 참조를 자동 갱신)
    op.rename_table("cosmetics", "user_cosmetics")
    op.execute("ALTER INDEX pk_cosmetics RENAME TO pk_user_cosmetics")
    op.execute("ALTER INDEX ix_cosmetics_deleted_at RENAME TO ix_user_cosmetics_deleted_at")
    op.execute("ALTER INDEX ix_cosmetics_user_id RENAME TO ix_user_cosmetics_user_id")

    # 2. skin_scans: 기존 JSON 컬럼 제거 → 개별 컬럼으로 분리
    op.drop_column("skin_scans", "scores")
    op.drop_column("skin_scans", "failure")
    op.drop_column("skin_scans", "questionnaire_answers")
    op.alter_column("skin_scans", "image_key", new_column_name="image_storage_key")

    # 3. skin_scans: ERD 기준 누락 컬럼 추가
    op.add_column("skin_scans", sa.Column("image_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("skin_scans", sa.Column("lighting_ok", sa.Boolean(), nullable=True))
    op.add_column("skin_scans", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("skin_scans", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("skin_scans", sa.Column("redness_score", sa.Float(), nullable=True))
    op.add_column("skin_scans", sa.Column("dryness_score", sa.Float(), nullable=True))
    op.add_column("skin_scans", sa.Column("oiliness_score", sa.Float(), nullable=True))
    op.add_column("skin_scans", sa.Column("redness_confidence", sa.Float(), nullable=True))
    op.add_column("skin_scans", sa.Column("dryness_confidence", sa.Float(), nullable=True))
    op.add_column("skin_scans", sa.Column("oiliness_confidence", sa.Float(), nullable=True))

    op.add_column("skin_scans", sa.Column("failure_code", sa.String(length=50), nullable=True))
    op.add_column("skin_scans", sa.Column("failure_retryable", sa.Boolean(), nullable=True))

    op.add_column("skin_scans", sa.Column("model_provider", sa.String(length=100), nullable=True))
    op.add_column("skin_scans", sa.Column("model_name", sa.String(length=100), nullable=True))
    op.add_column("skin_scans", sa.Column("model_version", sa.String(length=50), nullable=True))
    op.add_column("skin_scans", sa.Column("schema_version", sa.String(length=50), nullable=True))
    op.add_column("skin_scans", sa.Column("quality", sa.JSON(), nullable=True))

    # 4. skin_questionnaire_answers 신설 (문진 답변 별도 테이블)
    op.create_table(
        "skin_questionnaire_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_version", sa.String(length=20), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["skin_scans.id"],
            ondelete="CASCADE",
            name=op.f("fk_skin_questionnaire_answers_scan_id_skin_scans"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skin_questionnaire_answers")),
        sa.UniqueConstraint("scan_id", name=op.f("uq_skin_questionnaire_answers_scan_id")),
    )
    op.create_index(
        op.f("ix_skin_questionnaire_answers_scan_id"),
        "skin_questionnaire_answers",
        ["scan_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_skin_questionnaire_answers_scan_id"), table_name="skin_questionnaire_answers")
    op.drop_table("skin_questionnaire_answers")

    op.drop_column("skin_scans", "quality")
    op.drop_column("skin_scans", "schema_version")
    op.drop_column("skin_scans", "model_version")
    op.drop_column("skin_scans", "model_name")
    op.drop_column("skin_scans", "model_provider")
    op.drop_column("skin_scans", "failure_retryable")
    op.drop_column("skin_scans", "failure_code")
    op.drop_column("skin_scans", "oiliness_confidence")
    op.drop_column("skin_scans", "dryness_confidence")
    op.drop_column("skin_scans", "redness_confidence")
    op.drop_column("skin_scans", "oiliness_score")
    op.drop_column("skin_scans", "dryness_score")
    op.drop_column("skin_scans", "redness_score")
    op.drop_column("skin_scans", "completed_at")
    op.drop_column("skin_scans", "captured_at")
    op.drop_column("skin_scans", "lighting_ok")
    op.drop_column("skin_scans", "image_deleted_at")
    op.alter_column("skin_scans", "image_storage_key", new_column_name="image_key")
    op.add_column("skin_scans", sa.Column("questionnaire_answers", sa.JSON(), nullable=True))
    op.add_column("skin_scans", sa.Column("failure", sa.JSON(), nullable=True))
    op.add_column("skin_scans", sa.Column("scores", sa.JSON(), nullable=True))

    op.execute("ALTER INDEX ix_user_cosmetics_user_id RENAME TO ix_cosmetics_user_id")
    op.execute("ALTER INDEX ix_user_cosmetics_deleted_at RENAME TO ix_cosmetics_deleted_at")
    op.execute("ALTER INDEX pk_user_cosmetics RENAME TO pk_cosmetics")
    op.rename_table("user_cosmetics", "cosmetics")
