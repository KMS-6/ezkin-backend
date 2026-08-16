from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

# --- Eligibility ---


class EligibilityResponse(BaseModel):
    available_days: int
    required_days: int
    eligible: bool
    missing_inputs: list[str]


# --- Report ---


class ReportRequest(BaseModel):
    period_days: int = 14  # 14 or 30


class ReportPeriod(BaseModel):
    start_date: date
    end_date: date
    period_days: int


class ReportAccepted(BaseModel):
    report_id: UUID
    status: str = "processing"
    status_url: str


class ReportResult(BaseModel):
    report_id: UUID
    status: str
    period: ReportPeriod
    summary: str
    observations: list[str]
    patterns: list[str]
    recommendations: list[str]
    limitations: list[str]
    safety_status: str
    generated_at: datetime


# --- Pattern Analysis ---


class PatternAnalysisOut(BaseModel):
    scan_id: UUID
    window: str
    raw_facts: list[str]
    observed_pattern: str | None
    common_knowledge: None
    disclaimer: str
