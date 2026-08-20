from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.triggers.logic import is_self_harm, is_urgent

router = APIRouter(prefix="/quick-care", tags=["quick-care"])


class SafetyCheckRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class SafetyCheckResponse(BaseModel):
    action: str
    reply: str
    professional_help_suggested: bool


@router.post("/safety-check", response_model=SafetyCheckResponse)
async def safety_check(payload: SafetyCheckRequest) -> SafetyCheckResponse:
    # 14절: 자해·자살 표현은 나머지 위급 증상보다 먼저 검사해 위기 상담 안내로 전환한다.
    if is_self_harm(payload.message):
        return SafetyCheckResponse(
            action="stop_ai_guidance",
            reply="혼자 견디지 않으셔도 돼요. 지금 많이 힘드시다면 1393(자살예방상담전화) 등 "
            "전문 상담기관에 즉시 연락해 도움을 받아 주세요.",
            professional_help_suggested=True,
        )
    if is_urgent(payload.message):
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
