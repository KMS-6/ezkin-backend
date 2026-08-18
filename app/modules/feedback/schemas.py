from enum import StrEnum

from pydantic import BaseModel


class FeedbackRating(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class FeedbackReasonCode(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    FACTUALLY_WRONG = "factually_wrong"
    NOT_PERSONALIZED = "not_personalized"
    TOO_ALARMIST = "too_alarmist"
    UNSAFE_MEDICAL_EXPRESSION = "unsafe_medical_expression"
    WRONG_PRODUCT = "wrong_product"
    MISSING_CONTEXT = "missing_context"


class FeedbackIn(BaseModel):
    rating: FeedbackRating
    reason_code: FeedbackReasonCode | None = None
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: str
    generation_id: str
    rating: str
    reason_code: str | None
    comment: str | None
