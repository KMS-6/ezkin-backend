from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.triggers.schemas import ObservedPattern, PatternWindow, RawFact

# --- Eligibility ---


class EligibilityResponse(BaseModel):
    available_days: int
    required_days: int
    eligible: bool
    missing_inputs: list[str]


# --- Report ---


class ReportRequest(BaseModel):
    period_days: int = Field(default=14, ge=1)
    end_date: date | None = None
    locale: str = "ko-KR"


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


class ReportResult(BaseModel):
    report_id: UUID
    status: str
    period: ReportPeriod
    summary: str
    observations: list[ReportEvidence]
    patterns: list[ReportEvidence]
    recommendations: list[ReportEvidence]
    limitations: str
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
