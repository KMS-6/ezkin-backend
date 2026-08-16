from datetime import date, datetime

from pydantic import BaseModel


class RiskAssessmentOut(BaseModel):
    date: date
    risk_level: str
    risk_levels_enum: list[str]
    contributing_factors: list[str]
    limitation_notice: str


class EligibilityResponse(BaseModel):
    available_days: int
    required_days: int
    eligible: bool
    missing_inputs: list[str]


class ReportCreateIn(BaseModel):
    period_days: int
    end_date: date | None = None
    locale: str = "ko-KR"


class ReportAccepted(BaseModel):
    report_id: str
    status: str
    status_url: str


class ReportEvidence(BaseModel):
    text: str
    evidence_ids: list[str]


class ReportResult(BaseModel):
    report_id: str
    status: str
    period: dict | None = None
    summary: str | None = None
    observations: list[ReportEvidence] | None = None
    patterns: list[ReportEvidence] | None = None
    recommendations: list[ReportEvidence] | None = None
    limitations: str | None = None
    safety_status: str | None = None
    generated_at: datetime | None = None
