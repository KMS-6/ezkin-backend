from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.persona import get_persona_id
from app.db.session import get_db
from app.modules.reports import schemas, service
from app.modules.reports.pattern import analyze_pattern

router = APIRouter(tags=["reports"])

ALLOWED_PERIOD_DAYS = (14, 30)

DbDep = Annotated[AsyncSession, Depends(get_db)]
PersonaDep = Annotated[str, Depends(get_persona_id)]


@router.get("/analysis/eligibility", response_model=schemas.EligibilityResponse)
async def get_eligibility(
    db: DbDep,
    persona_id: PersonaDep,
    period_days: Annotated[int, Query(ge=14)] = 14,
) -> schemas.EligibilityResponse:
    result = await service.get_eligibility(db, persona_id, period_days)
    return schemas.EligibilityResponse(**result)


@router.post("/reports", response_model=schemas.ReportAccepted, status_code=202)
async def create_report(
    db: DbDep,
    persona_id: PersonaDep,
    payload: schemas.ReportRequest,
) -> schemas.ReportAccepted:
    if payload.period_days not in ALLOWED_PERIOD_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_report_period"},
        )
    report = await service.create_report(
        db, persona_id, payload.period_days, end_date=payload.end_date
    )
    return schemas.ReportAccepted(
        report_id=report.id,
        status=report.status,
        status_url=f"/api/v1/reports/{report.id}",
    )


def _evidence(items: list[dict]) -> list[schemas.ReportEvidence]:
    return [schemas.ReportEvidence(**item) for item in items]


@router.get("/reports/{report_id}", response_model=schemas.ReportResult)
async def get_report(
    report_id: UUID,
    db: DbDep,
    persona_id: PersonaDep,
) -> schemas.ReportResult:
    report = await service.get_report(db, persona_id, report_id)
    result = report.result or {}
    return schemas.ReportResult(
        report_id=report.id,
        status=report.status,
        period=schemas.ReportPeriod(
            start_date=report.start_date,
            end_date=report.end_date,
            period_days=report.period_days,
        ),
        summary=result.get("summary", ""),
        observations=_evidence(result.get("observations", [])),
        patterns=_evidence(result.get("patterns", [])),
        recommendations=_evidence(result.get("recommendations", [])),
        limitations=result.get("limitations", ""),
        safety_status=report.safety_status or "unknown",
        generated_at=report.generated_at,
    )


@router.get("/pattern-analysis", response_model=schemas.PatternAnalysisOut)
async def get_pattern_analysis(
    db: DbDep,
    persona_id: PersonaDep,
    scan_id: Annotated[UUID, Query()],
) -> schemas.PatternAnalysisOut:
    result = await analyze_pattern(db, persona_id, scan_id)
    return schemas.PatternAnalysisOut(
        scan_id=result["scan_id"],
        window=result["window"],
        raw_facts=result["raw_facts"],
        observed_pattern=result["observed_pattern"],
        common_knowledge=None,
        disclaimer=result["disclaimer"],
    )
