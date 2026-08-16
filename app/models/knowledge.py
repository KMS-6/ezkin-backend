from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Source document metadata for the common-knowledge RAG corpus.

    Retrieval over this corpus is not implemented (see docs/openapi.yaml); this
    table only tracks admin authoring/approval metadata for future indexing.
    """

    __tablename__ = "knowledge_documents"

    source_url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(200))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    license: Mapped[str | None] = mapped_column(String(100))
    source_type_note: Mapped[str | None] = mapped_column(String(300))
    review_status: Mapped[str] = mapped_column(String(20), default="draft")

    claim_id: Mapped[str | None] = mapped_column(String(60))
    claim_version: Mapped[int | None] = mapped_column(Integer)
    topic: Mapped[str | None] = mapped_column(String(100))
    population: Mapped[str | None] = mapped_column(String(200))
    evidence_level: Mapped[str | None] = mapped_column(String(20))
    allowed_features: Mapped[list[str] | None] = mapped_column(JSON)
    required_user_facts: Mapped[list[str] | None] = mapped_column(JSON)
    allowed_expressions: Mapped[str | None] = mapped_column(String(500))
    forbidden_expressions: Mapped[str | None] = mapped_column(String(500))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeIndex(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_indexes"

    version: Mapped[str] = mapped_column(String(30), unique=True)
    claim_ids: Mapped[list[str]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
