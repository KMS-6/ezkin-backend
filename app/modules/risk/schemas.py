from datetime import date

from pydantic import BaseModel


class RiskAssessmentOut(BaseModel):
    date: date
    risk_level: str
    risk_levels_enum: list[str]
    contributing_factors: list[str]
    limitation_notice: str
