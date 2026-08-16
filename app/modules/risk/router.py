from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.models.generation import Generation
from app.models.report import Report
from app.modules.risk.logic import (
    RISK_LEVELS,
    build_report_content,
    count_observation_days,
    load_today_risk_context,
)
from app.modules.risk.schemas import (
    EligibilityResponse,
    ReportAccepted,
    ReportCreateIn,
    ReportEvidence,
    ReportResult,
    RiskAssessmentOut,
)

router = APIRouter(tags=["risk"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]

KST = ZoneInfo("Asia/Seoul")
ELIGIBILITY_WINDOW_DAYS = 14


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


@router.get("/analysis/eligibility", response_model=EligibilityResponse)
async def get_analysis_eligibility(db: DbSession, persona_id: PersonaId) -> EligibilityResponse:
    available_days = await count_observation_days(db, persona_id, ELIGIBILITY_WINDOW_DAYS)
    eligible = available_days >= ELIGIBILITY_WINDOW_DAYS
    return EligibilityResponse(
        available_days=available_days,
        required_days=ELIGIBILITY_WINDOW_DAYS,
        eligible=eligible,
        missing_inputs=[] if eligible else ["skin_observation"],
    )


@router.post("/reports", response_model=ReportAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    payload: ReportCreateIn, db: DbSession, persona_id: PersonaId
) -> ReportAccepted:
    if payload.period_days not in (14, 30):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_report_period: period_days는 14 또는 30만 허용됩니다.",
        )

    available_days = await count_observation_days(db, persona_id, payload.period_days)
    if available_days < payload.period_days:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="insufficient_data_history: 리포트 생성에 필요한 관찰 데이터가 부족합니다.",
        )

    content = await build_report_content(db, persona_id, payload.period_days)
    report = Report(
        persona_id=persona_id,
        period_days=payload.period_days,
        end_date=payload.end_date or date.today(),
        locale=payload.locale,
        status="completed",
        generated_at=datetime.now(UTC),
        **content,
    )
    db.add(report)
    await db.flush()
    db.add(Generation(id=str(report.id), persona_id=persona_id, kind="report"))
    await db.commit()

    return ReportAccepted(
        report_id=str(report.id),
        status="processing",
        status_url=f"{settings.api_prefix}/reports/{report.id}",
    )


@router.get("/reports/{report_id}", response_model=ReportResult)
async def get_report(report_id: UUID, db: DbSession, persona_id: PersonaId) -> ReportResult:
    report = await db.get(Report, report_id)
    if report is None or report.persona_id != persona_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="리포트를 찾을 수 없습니다."
        )

    def _evidence(items: list[dict] | None) -> list[ReportEvidence] | None:
        return [ReportEvidence(**item) for item in items] if items is not None else None

    return ReportResult(
        report_id=str(report.id),
        status=report.status,
        period=report.period,
        summary=report.summary,
        observations=_evidence(report.observations),
        patterns=_evidence(report.patterns),
        recommendations=_evidence(report.recommendations),
        limitations=report.limitations,
        safety_status=report.safety_status,
        generated_at=report.generated_at,
    )
