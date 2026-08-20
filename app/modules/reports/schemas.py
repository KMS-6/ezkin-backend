from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.modules.triggers.schemas import ObservedPattern, PatternWindow, RawFact

# --- Eligibility ---


class EligibilityResponse(BaseModel):
    available_days: int
    required_days: int
    eligible: bool
    missing_inputs: list[str]


# --- Report ---


class ReportRequest(BaseModel):
    period_days: Literal[14, 30] = 14
    end_date: date | None = None
    locale: Literal["ko-KR"] = "ko-KR"


class ReportPeriod(BaseModel):
    start_date: date
    end_date: date
    period_days: int


class ReportAccepted(BaseModel):
    report_id: UUID
    status: str = "processing"
    status_url: str


class ReportEvidence(BaseModel):
    text: str
    evidence_ids: list[str]


class ReportClaim(BaseModel):
    claim_id: str
    version: int
    sentence: str
    topic: str


class ReportResult(BaseModel):
    report_id: UUID
    status: str
    period: ReportPeriod
    summary: str
    observations: list[ReportEvidence]
    patterns: list[ReportEvidence]
    recommendations: list[ReportEvidence]
    limitations: str
    common_knowledge: list[ReportClaim] = []
    safety_status: str
    generated_at: datetime | None = None


# --- Pattern Analysis ---


class PatternAnalysisOut(BaseModel):
    scan_id: UUID
    window: PatternWindow
    raw_facts: list[RawFact]
    observed_pattern: ObservedPattern | None
    common_knowledge: dict | None
    disclaimer: str
