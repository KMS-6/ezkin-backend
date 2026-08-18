from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SkinScan

_WINDOW_HOURS = 72
_PATTERN_THRESHOLD = 3  # 동시발생 최소 횟수


async def analyze_pattern(
    db: AsyncSession,
    persona_id: str,
    scan_id: UUID,
) -> dict[str, Any]:
    """scan 전후 72시간 패턴 분석."""
    # 대상 스캔 조회
    stmt = select(SkinScan).where(SkinScan.id == scan_id, SkinScan.persona_id == persona_id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()

    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "scan_not_found"}
        )

    if scan.scores is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "scan_has_no_scores"},
        )

    # 72시간 윈도우 내 주변 스캔 조회
    window_start = scan.created_at - timedelta(hours=_WINDOW_HOURS)
    window_end = scan.created_at + timedelta(hours=_WINDOW_HOURS)

    surrounding_stmt = (
        select(SkinScan)
        .where(
            SkinScan.persona_id == persona_id,
            SkinScan.id != scan_id,
            SkinScan.created_at >= window_start,
            SkinScan.created_at <= window_end,
            SkinScan.scores.is_not(None),
        )
        .order_by(SkinScan.created_at)
    )
    surrounding_result = await db.execute(surrounding_stmt)
    surrounding_scans = surrounding_result.scalars().all()

    # 원시 사실 구성 (시간순 정렬)
    all_scans = sorted([scan] + list(surrounding_scans), key=lambda s: s.created_at)
    raw_facts = _build_raw_facts(all_scans)

    # 동시발생 패턴 감지 (임계값 이상일 때만)
    observed_pattern = _detect_pattern(all_scans)

    return {
        "scan_id": str(scan_id),
        "window": "72h",
        "raw_facts": raw_facts,
        "observed_pattern": observed_pattern,
        "common_knowledge": None,
        "disclaimer": "이 분석은 관찰된 데이터의 패턴 기록이며 의료적 진단이 아닙니다.",
    }


def _build_raw_facts(scans: list[SkinScan]) -> list[str]:
    """스캔 데이터를 원시 사실 문장으로 변환한다."""
    facts = []
    for scan in scans:
        if scan.scores is None:
            continue
        date_str = scan.created_at.strftime("%Y-%m-%d %H:%M")
        for metric, value in scan.scores.items():
            facts.append(f"{date_str}에 {metric} 점수가 {value:.2f}였습니다.")
    return facts


def _detect_pattern(scans: list[SkinScan]) -> str | None:
    """동시발생이 3회 이상인 패턴을 탐지한다."""
    # 점수가 0.5 이상인 스캔 카운트 (고값 동시발생)
    high_value_count = sum(
        1 for s in scans if s.scores and any(v >= 0.5 for v in s.scores.values())
    )

    if high_value_count >= _PATTERN_THRESHOLD:
        return f"72시간 윈도우 내 점수가 0.5 이상인 측정이 {high_value_count}회 관찰됐습니다."

    return None
