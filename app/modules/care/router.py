from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.care.rules import CareInputs, CareMode, select_care_mode

router = APIRouter(prefix="/care-contexts", tags=["care"])


class CareContextPreviewRequest(BaseModel):
    humidity: float | None = None
    uv_index: float | None = None
    user_reports_discomfort: bool = False


class ObservedFactor(BaseModel):
    type: str
    message: str


class CareContextPreviewResponse(BaseModel):
    date: date
    care_mode: CareMode
    observed_factors: list[ObservedFactor]
    notice: str


@router.post("/preview", response_model=CareContextPreviewResponse)
async def preview_care_context(payload: CareContextPreviewRequest) -> CareContextPreviewResponse:
    inputs = CareInputs(
        humidity=payload.humidity,
        uv_index=payload.uv_index,
        user_reports_discomfort=payload.user_reports_discomfort,
    )
    factors: list[ObservedFactor] = []
    if inputs.humidity is not None and inputs.humidity < 40:
        factors.append(ObservedFactor(type="low_humidity", message="오늘 습도가 낮아요."))
    if inputs.uv_index is not None and inputs.uv_index >= 6:
        factors.append(ObservedFactor(type="high_uv", message="오늘 자외선 지수가 높아요."))
    if inputs.user_reports_discomfort:
        factors.append(
            ObservedFactor(type="reported_discomfort", message="사용자가 불편함을 기록했어요.")
        )
    return CareContextPreviewResponse(
        date=date.today(),
        care_mode=select_care_mode(inputs),
        observed_factors=factors,
        notice="생활·환경 데이터를 활용한 비의료적 피부 관리 참고 정보입니다.",
    )
