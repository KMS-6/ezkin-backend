from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.modules.reports.aggregator import aggregate_scans, check_eligibility
from app.modules.reports.safety import is_safe


async def get_eligibility(
    db: AsyncSession,
    persona_id: str,
    period_days: int,
) -> dict[str, Any]:
    as_of = date.today()
    return await check_eligibility(db, persona_id, period_days, as_of)


async def create_report(
    db: AsyncSession,
    persona_id: str,
    period_days: int,
) -> Report:
    as_of = date.today()
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
    """리포트를 집계하고 결과를 저장한다."""
    rows = await aggregate_scans(db, persona_id, period_days, as_of)

    # 원시 사실 기반 요약 생성
    total_days = len(rows)
    valid_rows = [r for r in rows if r["avg_scores"]]
    high_flushing_days = sum(1 for r in valid_rows if r["avg_scores"].get("flushing", 0) >= 0.5)

    summary = f"지난 {period_days}일 중 {total_days}일의 데이터가 확인됐습니다."
    observations = []
    if valid_rows:
        observations.append(
            f"{total_days}일 중 {high_flushing_days}일에 홍조 점수가 0.5 이상이었습니다."
        )
        avg_moisture = sum(r["avg_scores"].get("moisture", 0) for r in valid_rows) / len(valid_rows)
        observations.append(f"기간 평균 수분 지수는 {avg_moisture:.2f}였습니다.")

    patterns: list[str] = []
    # 단순 패턴 감지: 홍조 점수 상승일 + 수분 낮은 날 동시 발생
    co_occurrence = sum(
        1
        for r in valid_rows
        if r["avg_scores"].get("flushing", 0) >= 0.5 and r["avg_scores"].get("moisture", 1) < 0.4
    )
    if co_occurrence >= 3:
        patterns.append(
            f"홍조 점수 상승일과 수분 지수 0.4 미만이 함께 나타난 경우가 "
            f"{co_occurrence}회 있었습니다."
        )

    recommendations = [
        "관찰된 패턴을 바탕으로 보습제를 아침저녁으로 적용해 보세요.",
        "피부 관리 참고 정보이며 의료 진단을 대체하지 않습니다.",
    ]
    limitations = [
        "이 리포트는 입력된 데이터의 통계적 관찰이며 의료적 진단이 아닙니다.",
        f"분석 기간: {period_days}일 / 유효 데이터: {total_days}일",
    ]

    # 안전 필터 적용
    all_texts = [summary] + observations + patterns + recommendations + limitations
    if not all(is_safe(t) for t in all_texts):
        report.status = "failed"
        report.error_code = "safety_filter_triggered"
        await db.commit()
        return

    result_payload: dict[str, Any] = {
        "summary": summary,
        "observations": observations,
        "patterns": patterns,
        "recommendations": recommendations,
        "limitations": limitations,
    }

    report.status = "completed"
    report.result = result_payload
    report.safety_status = "passed"
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
