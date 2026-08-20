from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SkinScan


async def check_eligibility(
    db: AsyncSession,
    persona_id: str,
    period_days: int,
    as_of: date,
) -> dict[str, Any]:
    """리포트 생성 가능 여부를 확인한다."""
    start = as_of - timedelta(days=period_days - 1)

    # completed + scores 있는 스캔의 날짜 목록
    stmt = (
        select(func.date(SkinScan.captured_at))
        .where(
            SkinScan.persona_id == persona_id,
            SkinScan.status == "completed",
            or_(
                SkinScan.redness_score.is_not(None),
                SkinScan.dryness_score.is_not(None),
                SkinScan.oiliness_score.is_not(None),
            ),
            func.date(SkinScan.captured_at) >= start,
            func.date(SkinScan.captured_at) <= as_of,
        )
        .distinct()
    )
    result = await db.execute(stmt)
    available_days = len(result.scalars().all())

    eligible = available_days >= period_days
    return {
        "available_days": available_days,
        "required_days": period_days,
        "eligible": eligible,
        "missing_inputs": [] if eligible else ["scan_history"],
    }


async def aggregate_scans(
    db: AsyncSession,
    persona_id: str,
    period_days: int,
    as_of: date,
) -> list[dict[str, Any]]:
    """기간 내 스캔을 날짜별로 집계해 반환한다."""
    start = as_of - timedelta(days=period_days - 1)

    stmt = (
        select(SkinScan)
        .where(
            SkinScan.persona_id == persona_id,
            SkinScan.status == "completed",
            func.date(SkinScan.captured_at) >= start,
            func.date(SkinScan.captured_at) <= as_of,
        )
        .order_by(SkinScan.captured_at)
    )
    result = await db.execute(stmt)
    scans = result.scalars().all()

    # 날짜별 그룹화 후 평균 집계
    by_date: dict[date, list[dict]] = {}
    for scan in scans:
        d = scan.created_at.date()
        if d not in by_date:
            by_date[d] = []
        if scan.scores is not None:
            by_date[d].append(scan.scores)

    rows: list[dict[str, Any]] = []
    for d, score_list in sorted(by_date.items()):
        if score_list:
            keys = sorted({k for s in score_list for k in s.keys()})
            avg = {k: sum(s.get(k, 0) for s in score_list) / len(score_list) for k in keys}
            rows.append({"metric_date": d, "avg_scores": avg})
        else:
            rows.append({"metric_date": d, "avg_scores": None})

    return rows
