from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.modules.risk.logic import RISK_LEVELS, load_today_risk_context
from app.modules.risk.schemas import RiskAssessmentOut

router = APIRouter(tags=["risk"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]

KST = ZoneInfo("Asia/Seoul")


@router.get("/risk-assessments/today", response_model=RiskAssessmentOut)
async def get_today_risk_assessment(db: DbSession, persona_id: PersonaId) -> RiskAssessmentOut:
    now = datetime.now(KST)
    today = now.date()

    context = await load_today_risk_context(db, persona_id, today, now)

    return RiskAssessmentOut(
        date=today,
        risk_level=context["risk_level"],
        risk_levels_enum=RISK_LEVELS,
        contributing_factors=[text for _, text in context["factors"]],
        limitation_notice="의료적 진단이 아닌 생활·환경 데이터 기반의 참고 위험도입니다.",
    )
