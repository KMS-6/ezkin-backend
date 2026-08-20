from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class SosSessionOut(BaseModel):
    session_id: str
    quick_replies: list[str]


class SosMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        # 15.3절: 공백 제거 후 1~1,000자, 빈 문자열·제어 문자만 있는 입력은 422.
        stripped = value.strip()
        if not stripped or not any(ch.isprintable() for ch in stripped):
            raise ValueError("message는 공백 또는 제어 문자만으로 구성될 수 없습니다.")
        return stripped


class SosMessageOut(BaseModel):
    message_id: str
    reply_type: str
    reply: str
    matched_faq: dict | None
    decision: dict | None
    referenced_cosmetic_ids: list[str]
    used_contexts: list[str]
    safety_flag: str | None
    expert_referral_suggested: bool
