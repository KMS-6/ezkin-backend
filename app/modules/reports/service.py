from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation import Generation
from app.models.report import Report
from app.modules.reports.aggregator import check_eligibility
from app.modules.reports.knowledge import select_report_common_knowledge
from app.modules.reports.narration import narrate_report
from app.modules.reports.safety import is_safe
from app.modules.risk.logic import build_report_content


async def get_eligibility(
    db: AsyncSession,
    persona_id: str,
    period_days: int,
) -> dict[str, Any]:
    as_of = datetime.now(UTC).date()
    return await check_eligibility(db, persona_id, period_days, as_of)


async def create_report(
    db: AsyncSession,
    persona_id: str,
    period_days: int,
    end_date: date | None = None,
) -> Report:
    as_of = end_date or datetime.now(UTC).date()
    eligibility = await check_eligibility(db, persona_id, period_days, as_of)

    if not eligibility["eligible"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "insufficient_data_history"},
        )

    start_date = as_of - timedelta(days=period_days - 1)
    report = Report(
        persona_id=persona_id,
        period_days=period_days,
        start_date=start_date,
        end_date=as_of,
        status="processing",
    )
    db.add(report)
    await db.flush()
    db.add(Generation(id=str(report.id), persona_id=persona_id, kind="report"))
    await db.commit()
    await db.refresh(report)

    # 동기 방식으로 즉시 처리 (해커톤 — 백그라운드 태스크 생략)
    await _process_report(db, report, persona_id, period_days, as_of)

    return report


async def _process_report(
    db: AsyncSession,
    report: Report,
    persona_id: str,
    period_days: int,
    as_of: date,
) -> None:
    """리포트를 집계하고 결과를 저장한다(evidence_ids 기반, API명세서.md 기능 2절)."""
    content = await build_report_content(db, persona_id, period_days, as_of)
    common_knowledge = await select_report_common_knowledge(
        db, persona_id, report.start_date, as_of
    )

    narrated_summary = await narrate_report(content)
    if narrated_summary is not None:
        content["summary"] = narrated_summary

    all_texts = (
        [content["summary"]]
        + [item["text"] for item in content["observations"]]
        + [item["text"] for item in content["patterns"]]
        + [item["text"] for item in content["recommendations"]]
        + [content["limitations"]]
    )
    if not all(is_safe(t) for t in all_texts):
        report.status = "failed"
        report.error_code = "safety_filter_triggered"
        await db.commit()
        return

    result_payload: dict[str, Any] = {
        "summary": content["summary"],
        "observations": content["observations"],
        "patterns": content["patterns"],
        "recommendations": content["recommendations"],
        "limitations": content["limitations"],
        "common_knowledge": common_knowledge,
    }

    report.status = "completed"
    report.result = result_payload
    report.safety_status = content["safety_status"]
    report.generated_at = datetime.now(tz=UTC)
    await db.commit()


async def get_report(
    db: AsyncSession,
    persona_id: str,
    report_id: UUID,
) -> Report:
    stmt = select(Report).where(Report.id == report_id, Report.persona_id == persona_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "report_not_found"}
        )

    return report
