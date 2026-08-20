from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SkinScan
from app.modules.triggers.logic import build_pattern_analysis


async def analyze_pattern(
    db: AsyncSession,
    persona_id: str,
    scan_id: UUID,
) -> dict[str, Any]:
    """완료된 스캔 기준 직전 72시간 패턴 분석(API명세서.md 기능 5절)."""
    stmt = select(SkinScan).where(SkinScan.id == scan_id, SkinScan.persona_id == persona_id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()

    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "scan_not_found"}
        )

    if scan.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "scan_not_completed"},
        )

    content = await build_pattern_analysis(db, scan)
    return {"scan_id": str(scan_id), **content}
