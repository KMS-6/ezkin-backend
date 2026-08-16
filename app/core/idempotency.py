import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.idempotency import IdempotencyRecord


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def check_idempotency(
    db: AsyncSession, *, scope: str, subject: str, key: str, payload: dict
) -> dict | None:
    """Return a replayed response body for a known key, or None to proceed.

    Raises 409 when the same key is reused with a different payload.
    """
    payload_hash = _hash_payload(payload)
    cutoff = datetime.now(UTC) - timedelta(hours=settings.idempotency_ttl_hours)
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.subject == subject,
            IdempotencyRecord.key == key,
            IdempotencyRecord.created_at >= cutoff,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.payload_hash != payload_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency_key_reused: 동일 키에 다른 요청 내용이 감지되었습니다.",
        )
    return record.response_body


async def store_idempotency(
    db: AsyncSession,
    *,
    scope: str,
    subject: str,
    key: str,
    payload: dict,
    response_status: int,
    response_body: dict,
) -> None:
    db.add(
        IdempotencyRecord(
            scope=scope,
            subject=subject,
            key=key,
            payload_hash=_hash_payload(payload),
            response_status=response_status,
            response_body=response_body,
        )
    )
    await db.flush()
