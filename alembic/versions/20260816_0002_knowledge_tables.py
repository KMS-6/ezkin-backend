"""지식 베이스(RAG) 문서, 청크, 인덱스 테이블 추가."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0002_knowledge"
down_revision: str | None = "20260816_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.alter_column("source_url", existing_type=sa.String(length=500), type_=sa.Text())
        batch_op.alter_column(
            "title", existing_type=sa.String(length=200), type_=sa.String(length=500)
        )
        batch_op.alter_column("license", existing_type=sa.String(length=100), type_=sa.Text())
        batch_op.alter_column(
            "source_type_note", existing_type=sa.String(length=300), type_=sa.Text()
        )
        batch_op.alter_column(
            "claim_id", existing_type=sa.String(length=60), type_=sa.String(length=100)
        )
        batch_op.alter_column("topic", existing_type=sa.String(length=100), type_=sa.Text())
        batch_op.alter_column("population", existing_type=sa.String(length=200), type_=sa.Text())
        batch_op.alter_column(
            "evidence_level", existing_type=sa.String(length=20), type_=sa.String(length=50)
        )
        batch_op.alter_column(
            "allowed_expressions", existing_type=sa.String(length=500), type_=sa.Text()
        )
        batch_op.alter_column(
            "forbidden_expressions", existing_type=sa.String(length=500), type_=sa.Text()
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

    with op.batch_alter_table("knowledge_indexes") as batch_op:
        batch_op.alter_column(
            "version", existing_type=sa.String(length=30), type_=sa.String(length=50)
        )
        batch_op.add_column(
            sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.alter_column("chunk_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("knowledge_indexes") as batch_op:
        batch_op.drop_column("chunk_count")
        batch_op.alter_column(
            "version", existing_type=sa.String(length=50), type_=sa.String(length=30)
        )

    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.alter_column(
            "forbidden_expressions", existing_type=sa.Text(), type_=sa.String(length=500)
        )
        batch_op.alter_column(
            "allowed_expressions", existing_type=sa.Text(), type_=sa.String(length=500)
        )
        batch_op.alter_column(
            "evidence_level", existing_type=sa.String(length=50), type_=sa.String(length=20)
        )
        batch_op.alter_column("population", existing_type=sa.Text(), type_=sa.String(length=200))
        batch_op.alter_column("topic", existing_type=sa.Text(), type_=sa.String(length=100))
        batch_op.alter_column(
            "claim_id", existing_type=sa.String(length=100), type_=sa.String(length=60)
        )
        batch_op.alter_column(
            "source_type_note", existing_type=sa.Text(), type_=sa.String(length=300)
        )
        batch_op.alter_column("license", existing_type=sa.Text(), type_=sa.String(length=100))
        batch_op.alter_column(
            "title", existing_type=sa.String(length=500), type_=sa.String(length=200)
        )
        batch_op.alter_column("source_url", existing_type=sa.Text(), type_=sa.String(length=500))
