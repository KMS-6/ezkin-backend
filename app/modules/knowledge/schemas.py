from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ── 문서 등록 ──────────────────────────────────────────────────────────────────


class DocumentCreateRequest(BaseModel):
    source_url: str
    title: str
    collected_at: datetime
    license: str | None = None
    source_type_note: str | None = None
    raw_text: str  # 청킹 대상 본문


class DocumentResponse(BaseModel):
    id: UUID
    source_url: str
    title: str
    collected_at: datetime
    review_status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 문서 승인 (Claim Card) ─────────────────────────────────────────────────────


class DocumentApproveRequest(BaseModel):
    claim_id: str
    claim_version: int
    topic: str | None = None
    population: str | None = None
    evidence_level: str | None = None
    allowed_features: list[str] | None = None
    required_user_facts: list[str] | None = None
    allowed_expressions: str | None = None
    forbidden_expressions: str | None = None
    next_review_at: datetime | None = None


class DocumentApproveResponse(BaseModel):
    id: UUID
    review_status: str
    claim_id: str
    claim_version: int

    model_config = {"from_attributes": True}


# ── 인덱스 ─────────────────────────────────────────────────────────────────────


class IndexCreateRequest(BaseModel):
    version: str
    claim_ids: list[str]


class IndexResponse(BaseModel):
    id: UUID
    version: str
    is_active: bool
    claim_ids: list[str]
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 내부 검색 ─────────────────────────────────────────────────────────────────


class KnowledgeSearchRequest(BaseModel):
    keywords: list[str]
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeChunkResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    score: int  # 매칭된 키워드 수


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeChunkResult]
