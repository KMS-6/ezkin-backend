from datetime import datetime

from pydantic import BaseModel


class PatternWindow(BaseModel):
    start: datetime
    end: datetime


class RawFact(BaseModel):
    type: str
    text: str


class ObservedPattern(BaseModel):
    text: str
    sample_size: int
    match_count: int


class PatternAnalysisOut(BaseModel):
    scan_id: str
    window: PatternWindow
    raw_facts: list[RawFact]
    observed_pattern: ObservedPattern | None
    common_knowledge: dict | None
    disclaimer: str


class SosSessionOut(BaseModel):
    session_id: str
    quick_replies: list[str]


class SosMessageIn(BaseModel):
    message: str


class SosMessageOut(BaseModel):
    message_id: str
    reply_type: str
    reply: str
    matched_faq: dict | None
    referenced_cosmetic_ids: list[str]
    safety_flag: str | None
    expert_referral_suggested: bool
