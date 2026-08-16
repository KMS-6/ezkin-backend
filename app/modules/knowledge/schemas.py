from datetime import datetime

from pydantic import BaseModel


class KnowledgeDocumentCreateIn(BaseModel):
    source_url: str
    title: str
    collected_at: datetime
    license: str | None = None
    source_type_note: str | None = None


class KnowledgeDocumentOut(BaseModel):
    id: str
    source_url: str
    title: str
    collected_at: datetime
    license: str | None
    review_status: str
    claim_id: str | None
    claim_version: int | None
    topic: str | None
    population: str | None
    evidence_level: str | None
    allowed_features: list[str] | None
    required_user_facts: list[str] | None
    next_review_at: datetime | None


class ClaimApproveIn(BaseModel):
    claim_id: str
    claim_version: int
    topic: str
    population: str
    evidence_level: str
    allowed_features: list[str]
    required_user_facts: list[str]
    allowed_expressions: str
    forbidden_expressions: str
    next_review_at: datetime


class KnowledgeIndexCreateIn(BaseModel):
    version: str


class KnowledgeIndexOut(BaseModel):
    version: str
    claim_ids: list[str]
    is_active: bool
