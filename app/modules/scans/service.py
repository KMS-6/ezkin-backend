import base64
import hashlib
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SkinScan
from app.modules.scans.schemas import CaptureMethod, SkinScanCreate

# 문진 severity → 점수 매핑
SEVERITY_SCORE: dict[str, float] = {"none": 0.0, "mild": 0.3, "moderate": 0.6, "severe": 1.0}

# 카메라 스캔 실패 고정 응답
_CAMERA_FAILURE = {
    "code": "model_not_implemented",
    "message": "이미지 분석 모델이 연동되지 않았습니다.",
    "retryable": False,
}


def _payload_hash(payload: SkinScanCreate) -> str:
    return hashlib.sha256(payload.model_dump_json().encode()).hexdigest()


def _compute_scores(answers: dict) -> dict[str, float]:
    return {
        "redness": SEVERITY_SCORE.get(answers.get("redness", "none"), 0.0),
        "dryness": SEVERITY_SCORE.get(answers.get("tightness", "none"), 0.0),
        "oiliness": SEVERITY_SCORE.get(answers.get("oiliness", "none"), 0.0),
    }


async def create_scan(
    db: AsyncSession,
    persona_id: str,
    payload: SkinScanCreate,
    idempotency_key: str,
) -> tuple[SkinScan, bool]:
    """스캔 생성 또는 idempotency 중복 반환. (scan, is_new) 반환."""
    payload_hash = _payload_hash(payload)

    # 동일 키 존재 확인
    existing = await db.execute(
        select(SkinScan).where(
            SkinScan.persona_id == persona_id,
            SkinScan.idempotency_key == idempotency_key,
        )
    )
    existing_scan = existing.scalar_one_or_none()

    if existing_scan is not None:
        if existing_scan.idempotency_payload_hash != payload_hash:
            # 같은 키, 다른 payload → 409
            raise ValueError("idempotency_conflict")
        return existing_scan, False

    # 신규 스캔 생성
    if payload.capture_method == CaptureMethod.CAMERA:
        scan = SkinScan(
            persona_id=persona_id,
            capture_method="camera",
            image_key=payload.image_key,
            status="failed",
            failure=_CAMERA_FAILURE,
            idempotency_key=idempotency_key,
            idempotency_payload_hash=payload_hash,
        )
    else:
        # questionnaire
        answers_dict = payload.answers.model_dump() if payload.answers else {}
        # new_lesions은 boolean이므로 severity 매핑에서 제외
        scores = _compute_scores(answers_dict)
        scan = SkinScan(
            persona_id=persona_id,
            capture_method="questionnaire",
            questionnaire_answers=answers_dict,
            scores=scores,
            status="completed",
            lower_accuracy=True,
            idempotency_key=idempotency_key,
            idempotency_payload_hash=payload_hash,
        )

    db.add(scan)
    try:
        await db.commit()
        await db.refresh(scan)
        return scan, True
    except IntegrityError as exc:
        await db.rollback()
        existing = await db.execute(
            select(SkinScan).where(
                SkinScan.persona_id == persona_id,
                SkinScan.idempotency_key == idempotency_key,
            )
        )
        existing_scan = existing.scalar_one_or_none()
        if existing_scan is not None:
            if existing_scan.idempotency_payload_hash != payload_hash:
                raise ValueError("idempotency_conflict") from exc
            return existing_scan, False
        raise


async def get_scan(
    db: AsyncSession,
    scan_id: UUID,
    persona_id: str,
) -> SkinScan | None:
    result = await db.execute(
        select(SkinScan).where(
            SkinScan.id == scan_id,
            SkinScan.persona_id == persona_id,
        )
    )
    return result.scalar_one_or_none()


def _encode_cursor(scan: SkinScan) -> str:
    """scan_id 를 base64 인코딩하여 커서로 반환."""
    return base64.urlsafe_b64encode(str(scan.id).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> UUID:
    """커서를 UUID로 디코딩."""
    padded = cursor + "=" * (-len(cursor) % 4)
    return UUID(base64.urlsafe_b64decode(padded).decode())


async def list_scans(
    db: AsyncSession,
    persona_id: str,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[SkinScan], str | None]:
    """커서 기반 페이지네이션. cursor = base64(scan_id).
    내부적으로 rowid(자동 정수) 또는 created_at을 기준으로 정렬.
    cursor scan보다 먼저 생성된 항목들을 반환.
    """
    query = select(SkinScan).where(SkinScan.persona_id == persona_id)

    if cursor is not None:
        cursor_id: UUID | None = None
        try:
            cursor_id = _decode_cursor(cursor)
        except ValueError:
            cursor_id = None

        if cursor_id is not None:
            cursor_scan_result = await db.execute(
                select(SkinScan).where(
                    SkinScan.id == cursor_id,
                    SkinScan.persona_id == persona_id,
                )
            )
            cursor_scan = cursor_scan_result.scalar_one_or_none()
            if cursor_scan is not None:
                # cursor_scan의 created_at보다 이전 OR (같은 시간이면 id 문자열이 더 작은 것)
                # SQLite에서 datetime은 text로 저장되므로 cast 없이 직접 비교
                cursor_created_at = cursor_scan.created_at
                cursor_id_val = cursor_scan.id
                query = query.where(
                    or_(
                        SkinScan.created_at < cursor_created_at,
                        (SkinScan.created_at == cursor_created_at) & (SkinScan.id < cursor_id_val),
                    )
                )

    query = query.order_by(SkinScan.created_at.desc(), SkinScan.id.desc()).limit(limit + 1)
    result = await db.execute(query)
    items = list(result.scalars())

    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = _encode_cursor(items[-1])

    return items, next_cursor
