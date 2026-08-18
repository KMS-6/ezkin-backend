"""지식 베이스(RAG) 문서, 청크, 인덱스 테이블 추가."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("source_type_note", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("claim_id", sa.String(length=100), nullable=True),
        sa.Column("claim_version", sa.Integer(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("population", sa.Text(), nullable=True),
        sa.Column("evidence_level", sa.String(length=50), nullable=True),
        sa.Column("allowed_features", sa.JSON(), nullable=True),
        sa.Column("required_user_facts", sa.JSON(), nullable=True),
        sa.Column("allowed_expressions", sa.Text(), nullable=True),
        sa.Column("forbidden_expressions", sa.Text(), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            name=op.f("fk_knowledge_chunks_document_id_knowledge_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_chunks")),
    )
    op.create_index(op.f("ix_knowledge_chunks_document_id"), "knowledge_chunks", ["document_id"])
    op.create_table(
        "knowledge_indexes",
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("claim_ids", sa.JSON(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_indexes")),
        sa.UniqueConstraint("version", name=op.f("uq_knowledge_indexes_version")),
    )


def downgrade() -> None:
    op.drop_table("knowledge_indexes")
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
