import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/quick-care", tags=["quick-care"])


class SafetyCheckRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class SafetyCheckResponse(BaseModel):
    action: str
    reply: str
    professional_help_suggested: bool


URGENT_KEYWORDS = ("호흡곤란", "숨을못", "의식", "심한부종", "눈이부어")


def _is_urgent(message: str) -> bool:
    # 공백 제거 후 비교해 "호흡 곤란" / "호흡곤란" 등 변형을 모두 감지
    normalized = re.sub(r"\s+", "", message)
    return any(keyword in normalized for keyword in URGENT_KEYWORDS)


@router.post("/safety-check", response_model=SafetyCheckResponse)
async def safety_check(payload: SafetyCheckRequest) -> SafetyCheckResponse:
    if _is_urgent(payload.message):
        return SafetyCheckResponse(
            action="stop_ai_guidance",
            reply="앱의 일반 관리 안내 범위를 벗어납니다. 즉시 의료기관에 문의해 주세요.",
            professional_help_suggested=True,
        )
    return SafetyCheckResponse(
        action="continue_general_guidance",
        reply="등록된 제품과 일반적인 피부 관리 범위에서 안내할 수 있어요.",
        professional_help_suggested=False,
    )
