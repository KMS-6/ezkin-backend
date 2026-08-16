from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.persona import get_persona_id
from app.db.session import get_db
from app.modules.scans import service
from app.modules.scans.schemas import (
    SkinScanAccepted,
    SkinScanCreate,
    SkinScanListResponse,
    SkinScanResponse,
)

router = APIRouter(prefix="/skin-scans", tags=["skin-scans"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]


@router.post("", response_model=SkinScanAccepted, status_code=status.HTTP_202_ACCEPTED)
async def submit_scan(
    payload: SkinScanCreate,
    db: DbSession,
    persona_id: PersonaId,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> SkinScanAccepted:
    try:
        scan, _ = await service.create_scan(db, persona_id, payload, idempotency_key)
    except ValueError as exc:
        if "idempotency_conflict" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "idempotency_conflict"},
            ) from exc
        raise

    response.headers["Location"] = f"/api/v1/skin-scans/{scan.id}"
    response.headers["Retry-After"] = "1"

    return SkinScanAccepted(
        scan_id=scan.id,
        status="processing",
        capture_method=payload.capture_method,
        status_url=f"/api/v1/skin-scans/{scan.id}",
    )


@router.get("/{scan_id}", response_model=SkinScanResponse)
async def get_scan(
    scan_id: UUID,
    db: DbSession,
    persona_id: PersonaId,
) -> SkinScanResponse:
    scan = await service.get_scan(db, scan_id, persona_id)
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="스캔을 찾을 수 없습니다.",
        )
    return SkinScanResponse.model_validate(scan)


@router.get("", response_model=SkinScanListResponse)
async def list_scans(
    db: DbSession,
    persona_id: PersonaId,
    limit: int = 20,
    cursor: str | None = None,
) -> SkinScanListResponse:
    items, next_cursor = await service.list_scans(db, persona_id, limit=limit, cursor=cursor)
    return SkinScanListResponse(
        items=[SkinScanResponse.model_validate(s) for s in items],
        next_cursor=next_cursor,
    )
