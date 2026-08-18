from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaptureMethod(StrEnum):
    CAMERA = "camera"
    QUESTIONNAIRE = "questionnaire"


class SeverityLevel(StrEnum):
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class QuestionnaireAnswers(BaseModel):
    redness: SeverityLevel
    tightness: SeverityLevel
    oiliness: SeverityLevel
    new_lesions: bool


# POST 요청 body
class SkinScanCreate(BaseModel):
    capture_method: CaptureMethod
    # 카메라 업로드 시
    image_key: str | None = Field(default=None, max_length=500)
    # 문진 시
    answers: QuestionnaireAnswers | None = None


# 202 응답
class SkinScanAccepted(BaseModel):
    scan_id: UUID
    status: str = "processing"
    capture_method: CaptureMethod
    status_url: str


# 스캔 결과 (GET)
class SkinScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: UUID = Field(alias="id")
    persona_id: str
    capture_method: str
    status: str
    lower_accuracy: bool
    image_key: str | None
    scores: dict | None
    failure: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# 목록 응답 (커서 기반 페이지네이션)
class SkinScanListResponse(BaseModel):
    items: list[SkinScanResponse]
    next_cursor: str | None = None
