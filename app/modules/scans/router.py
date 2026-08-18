import hashlib
import json
from datetime import UTC, date, datetime, time
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.idempotency import check_idempotency, store_idempotency
from app.core.mock_persona import get_persona_id
from app.core.storage import read_and_validate_image, store_bytes
from app.db.session import get_db
from app.models.scan import SkinScan
from app.modules.scans.analysis import score_questionnaire
from app.modules.scans.schemas import (
    SkinScanAccepted,
    SkinScanFailure,
    SkinScanListItem,
    SkinScanListResponse,
    SkinScanModel,
    SkinScanResult,
)

router = APIRouter(prefix="/skin-scans", tags=["skin-scans"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]

REQUIRED_QUESTIONS = {"redness", "tightness", "oiliness"}
ALLOWED_QUESTIONS = REQUIRED_QUESTIONS | {"new_lesions"}
SEVERITY_VALUES = {"none", "mild", "moderate", "severe"}

# delta_vs_baseline은 최근 유효 스캔 중앙값과의 차이. 기준선이 부족하면 null을 반환한다.
BASELINE_WINDOW = 10
BASELINE_MIN_SCANS = 3


def _validation_error(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


def _parse_answers(raw: str) -> list[dict]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _validation_error("answers는 JSON 배열이어야 합니다.") from exc
    if not isinstance(parsed, list):
        raise _validation_error("answers는 JSON 배열이어야 합니다.")

    seen: set[str] = set()
    for item in parsed:
        question_id = item.get("question_id") if isinstance(item, dict) else None
        value = item.get("value") if isinstance(item, dict) else None
        if question_id not in ALLOWED_QUESTIONS or value not in SEVERITY_VALUES:
            raise _validation_error("answers 형식이 올바르지 않습니다.")
        if question_id in seen:
            raise _validation_error("동일한 question_id를 중복 제출할 수 없습니다.")
        seen.add(question_id)
    if not REQUIRED_QUESTIONS.issubset(seen):
        raise _validation_error("redness, tightness, oiliness는 필수입니다.")
    return parsed


async def _latest_completed_scan(db: AsyncSession, persona_id: str) -> SkinScan | None:
    result = await db.execute(
        select(SkinScan)
        .where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
        .order_by(SkinScan.captured_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _recent_completed_scores(
    db: AsyncSession, persona_id: str, limit: int = BASELINE_WINDOW
) -> list[dict[str, float]]:
    result = await db.execute(
        select(SkinScan)
        .where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
        .order_by(SkinScan.captured_at.desc())
        .limit(limit)
    )
    return [scan.scores for scan in result.scalars() if scan.scores]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _compute_delta_vs_baseline(
    scores: dict[str, float], history: list[dict[str, float]]
) -> dict[str, float] | None:
    if len(history) < BASELINE_MIN_SCANS:
        return None
    deltas: dict[str, float] = {}
    for metric, value in scores.items():
        metric_values = [entry[metric] for entry in history if metric in entry]
        if len(metric_values) < BASELINE_MIN_SCANS:
            continue
        deltas[metric] = round(value - _median(metric_values), 2)
    return deltas or None


# 202 Accepted + status="processing"은 비동기 API 스펙 규격을 충족하기 위한 것으로, 실제로는
# 워커 큐 없이 이 요청 트랜잭션 내에서 즉시 status="completed"(questionnaire) 또는
# status="failed"(camera, 비전 모델 미연동)까지 계산해 커밋하는 동기 mock 처리다.
@router.post("", response_model=SkinScanAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_skin_scan(
    db: DbSession,
    persona_id: PersonaId,
    response: Response,
    captured_at: Annotated[datetime, Form()],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    capture_method: Annotated[str, Form()] = "camera",
    image: Annotated[UploadFile | None, File()] = None,
    questionnaire_version: Annotated[str | None, Form()] = None,
    answers: Annotated[str | None, Form()] = None,
    lighting_ok: Annotated[bool | None, Form()] = None,
) -> SkinScanAccepted:
    if capture_method not in {"camera", "questionnaire"}:
        raise _validation_error("capture_method는 camera 또는 questionnaire여야 합니다.")

    image_bytes: bytes | None = None
    parsed_answers: list[dict] | None = None
    if capture_method == "camera":
        if image is None:
            raise _validation_error("camera 방식은 image가 필요합니다.")
        image_bytes = await read_and_validate_image(image)
    else:
        if not questionnaire_version or not answers:
            raise _validation_error(
                "questionnaire 방식은 questionnaire_version과 answers가 필요합니다."
            )
        if questionnaire_version != "v1":
            raise _validation_error("지원하지 않는 questionnaire_version입니다.")
        parsed_answers = _parse_answers(answers)

    idempotency_payload = {
        "capture_method": capture_method,
        "captured_at": captured_at.isoformat(),
        "questionnaire_version": questionnaire_version,
        "answers": parsed_answers,
        "lighting_ok": lighting_ok,
        "image_sha256": hashlib.sha256(image_bytes).hexdigest() if image_bytes else None,
    }
    cached = await check_idempotency(
        db,
        scope="skin_scans:create",
        subject=persona_id,
        key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        response.headers["Location"] = cached["status_url"]
        response.headers["Retry-After"] = "3"
        return SkinScanAccepted(**cached)

    scan = SkinScan(
        persona_id=persona_id,
        capture_method=capture_method,
        captured_at=captured_at,
        lighting_ok=lighting_ok,
        questionnaire_version=questionnaire_version if capture_method == "questionnaire" else None,
        answers=parsed_answers,
    )

    if capture_method == "camera":
        assert image_bytes is not None
        scan.image_key = store_bytes(image_bytes, "skin-scans")
        scan.status = "failed"
        scan.failure_code = "model_not_implemented"
        scan.failure_message = "이미지 기반 분석 모델은 아직 연동되지 않았습니다."
        scan.failure_retryable = False
    else:
        assert parsed_answers is not None
        scores = score_questionnaire(parsed_answers)
        previous = await _latest_completed_scan(db, persona_id)
        baseline_history = await _recent_completed_scores(db, persona_id)
        scan.scores = scores
        scan.confidence = dict.fromkeys(scores, 0.5)
        scan.delta_vs_previous = (
            {
                metric: round(scores[metric] - previous.scores.get(metric, scores[metric]), 2)
                for metric in scores
            }
            if previous and previous.scores
            else None
        )
        scan.delta_vs_baseline = _compute_delta_vs_baseline(scores, baseline_history)
        scan.lower_accuracy = True
        scan.status = "completed"
        scan.limitation_notice = (
            "조명·기기 차이에 따라 오차가 있을 수 있는 개인 기준 참고 지표입니다."
        )

    db.add(scan)
    await db.flush()

    status_url = f"{settings.api_prefix}/skin-scans/{scan.id}"
    result = SkinScanAccepted(
        scan_id=str(scan.id),
        status="processing",
        capture_method=scan.capture_method,
        status_url=status_url,
    )
    cached = await store_idempotency(
        db,
        scope="skin_scans:create",
        subject=persona_id,
        key=idempotency_key,
        payload=idempotency_payload,
        response_status=status.HTTP_202_ACCEPTED,
        response_body=result.model_dump(),
    )
    if cached is not None:
        response.headers["Location"] = cached["status_url"]
        response.headers["Retry-After"] = "3"
        return SkinScanAccepted(**cached)

    await db.commit()

    response.headers["Location"] = status_url
    response.headers["Retry-After"] = "3"
    return result


@router.get("/{scan_id}", response_model=SkinScanResult)
async def get_skin_scan(scan_id: UUID, db: DbSession, persona_id: PersonaId) -> SkinScanResult:
    scan = await db.get(SkinScan, scan_id)
    if scan is None or scan.persona_id != persona_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="스캔을 찾을 수 없습니다."
        )
    return SkinScanResult(
        scan_id=str(scan.id),
        status=scan.status,
        capture_method=scan.capture_method,
        created_at=scan.created_at,
        lower_accuracy=scan.lower_accuracy,
        schema_version="skin_observation.v1" if scan.status == "completed" else None,
        scores=scan.scores,
        confidence=scan.confidence,
        delta_vs_baseline=scan.delta_vs_baseline,
        delta_vs_previous=scan.delta_vs_previous,
        model=(
            SkinScanModel(provider="TBD", name="TBD", version="TBD")
            if scan.status == "completed"
            else None
        ),
        limitation_notice=scan.limitation_notice,
        retry_after_seconds=3 if scan.status == "processing" else None,
        failure=(
            SkinScanFailure(
                code=scan.failure_code,
                message=scan.failure_message,
                retryable=scan.failure_retryable,
            )
            if scan.status == "failed"
            else None
        ),
    )


@router.get("", response_model=SkinScanListResponse)
async def list_skin_scans(
    db: DbSession,
    persona_id: PersonaId,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SkinScanListResponse:
    stmt = select(SkinScan).where(SkinScan.persona_id == persona_id)
    if from_:
        stmt = stmt.where(SkinScan.captured_at >= datetime.combine(from_, time.min, tzinfo=UTC))
    if to:
        stmt = stmt.where(SkinScan.captured_at <= datetime.combine(to, time.max, tzinfo=UTC))
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as exc:
            raise _validation_error("cursor 형식이 올바르지 않습니다.") from exc
        stmt = stmt.where(SkinScan.captured_at < cursor_dt)

    stmt = stmt.order_by(SkinScan.captured_at.desc(), SkinScan.id.desc()).limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())
    has_more = len(rows) > limit
    rows = rows[:limit]

    return SkinScanListResponse(
        items=[
            SkinScanListItem(scan_id=str(row.id), status=row.status, captured_at=row.captured_at)
            for row in rows
        ],
        next_cursor=rows[-1].captured_at.isoformat() if has_more and rows else None,
        has_more=has_more,
    )
