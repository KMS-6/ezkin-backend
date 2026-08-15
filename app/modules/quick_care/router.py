from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/quick-care", tags=["quick-care"])


class SafetyCheckRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class SafetyCheckResponse(BaseModel):
    action: str
    reply: str
    professional_help_suggested: bool


URGENT_KEYWORDS = ("호흡 곤란", "숨을 못", "의식", "심한 부종", "눈이 부어")


@router.post("/safety-check", response_model=SafetyCheckResponse)
async def safety_check(payload: SafetyCheckRequest) -> SafetyCheckResponse:
    if any(keyword in payload.message for keyword in URGENT_KEYWORDS):
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
