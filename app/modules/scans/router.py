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
from app.core.storage import read_and_validate_image
from app.db.session import get_db
from app.models.scan import SkinQuestionnaireAnswers, SkinScan
from app.modules.scans.analysis import score_questionnaire
from app.modules.scans.schemas import (
    SkinScanAccepted,
    SkinScanFailure,
    SkinScanListItem,
    SkinScanListResponse,
    SkinScanModel,
    SkinScanResult,
)
from app.modules.scans.vision import (
    VISION_MODEL_VERSION,
    VISION_PROVIDER,
    VISION_SCHEMA_VERSION,
    analyze_image,
)

router = APIRouter(prefix="/skin-scans", tags=["skin-scans"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]

REQUIRED_QUESTIONS = {"redness", "tightness", "oiliness"}
ALLOWED_QUESTIONS = REQUIRED_QUESTIONS | {"new_lesions"}
PERSISTED_SCORE_METRICS = {"redness", "dryness", "oiliness"}
SEVERITY_VALUES = {"none", "mild", "moderate", "severe"}

# delta_vs_baseline은 최근 유효 스캔 중앙값과의 차이. 기준선이 부족하면 null을 반환한다.
BASELINE_WINDOW = 10
BASELINE_MIN_SCANS = 3

_LIMITATION_NOTICE = "조명·기기 차이에 따라 오차가 있을 수 있는 개인 기준 참고 지표입니다."


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


async def _latest_completed_scan(
    db: AsyncSession, persona_id: str, exclude_scan_id: UUID | None = None
) -> SkinScan | None:
    stmt = select(SkinScan).where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
    if exclude_scan_id is not None:
        stmt = stmt.where(SkinScan.id != exclude_scan_id)
    result = await db.execute(stmt.order_by(SkinScan.captured_at.desc()).limit(1))
    return result.scalar_one_or_none()


async def _recent_completed_scores(
    db: AsyncSession,
    persona_id: str,
    exclude_scan_id: UUID | None = None,
    limit: int = BASELINE_WINDOW,
) -> list[dict[str, float]]:
    stmt = select(SkinScan).where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
    if exclude_scan_id is not None:
        stmt = stmt.where(SkinScan.id != exclude_scan_id)
    result = await db.execute(stmt.order_by(SkinScan.captured_at.desc()).limit(limit))
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
    )

    if capture_method == "camera":
        assert image_bytes is not None
        outcome = await analyze_image(image_bytes, image.content_type)
        if outcome is None:
            scan.status = "failed"
            scan.failure_code = "model_not_implemented"
            scan.failure_retryable = False
        elif outcome.failure_code is not None:
            scan.status = "failed"
            scan.failure_code = outcome.failure_code
            scan.failure_retryable = outcome.failure_retryable
        else:
            scan.scores = outcome.scores
            scan.confidence = outcome.confidence
            scan.lower_accuracy = False
            scan.status = "completed"
            scan.completed_at = datetime.now(UTC)
            scan.model_provider = outcome.model_provider
            scan.model_name = outcome.model_name
            scan.model_version = outcome.model_version
            scan.schema_version = outcome.schema_version
    else:
        assert parsed_answers is not None
        scores = {
            metric: score
            for metric, score in score_questionnaire(parsed_answers).items()
            if metric in PERSISTED_SCORE_METRICS
        }
        scan.scores = scores
        scan.confidence = dict.fromkeys(scores, 0.5)
        scan.lower_accuracy = True
        scan.status = "completed"
        scan.completed_at = datetime.now(UTC)
        scan.schema_version = VISION_SCHEMA_VERSION

    db.add(scan)
    await db.flush()

    if capture_method == "questionnaire" and parsed_answers:
        qa = SkinQuestionnaireAnswers(
            scan_id=scan.id,
            questionnaire_version=questionnaire_version or "v1",
            answers=parsed_answers,
            created_at=datetime.now(UTC),
        )
        db.add(qa)

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


def _scan_model(scan: SkinScan) -> SkinScanModel | None:
    if scan.status != "completed":
        return None
    if scan.model_provider and scan.model_name and scan.model_version:
        return SkinScanModel(
            provider=scan.model_provider,
            name=scan.model_name,
            version=scan.model_version,
        )
    if scan.capture_method == "camera":
        return SkinScanModel(
            provider=scan.model_provider or VISION_PROVIDER,
            name=scan.model_name or settings.vision_llm_model,
            version=scan.model_version or VISION_MODEL_VERSION,
        )
    # questionnaire 채점(analysis.py::score_questionnaire)은 외부 모델을 쓰지 않는
    # 규칙 기반 로직이라 실제 모델 메타데이터가 없다.
    return SkinScanModel(provider="TBD", name="TBD", version="TBD")


@router.get("/{scan_id}", response_model=SkinScanResult)
async def get_skin_scan(scan_id: UUID, db: DbSession, persona_id: PersonaId) -> SkinScanResult:
    scan = await db.get(SkinScan, scan_id)
    if scan is None or scan.persona_id != persona_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="스캔을 찾을 수 없습니다."
        )

    delta_vs_previous: dict[str, float] | None = None
    delta_vs_baseline: dict[str, float] | None = None
    if scan.status == "completed" and scan.scores:
        previous = await _latest_completed_scan(db, persona_id, scan.id)
        if previous and previous.scores:
            delta_vs_previous = {
                metric: round(
                    scan.scores[metric] - previous.scores.get(metric, scan.scores[metric]), 2
                )
                for metric in scan.scores
            }
        baseline_history = await _recent_completed_scores(db, persona_id, scan.id)
        delta_vs_baseline = _compute_delta_vs_baseline(scan.scores, baseline_history)

    return SkinScanResult(
        scan_id=str(scan.id),
        status=scan.status,
        capture_method=scan.capture_method,
        created_at=scan.created_at,
        lower_accuracy=scan.lower_accuracy,
        schema_version=(scan.schema_version or VISION_SCHEMA_VERSION)
        if scan.status == "completed"
        else None,
        scores=scan.scores,
        confidence=scan.confidence,
        delta_vs_baseline=delta_vs_baseline,
        delta_vs_previous=delta_vs_previous,
        model=_scan_model(scan),
        limitation_notice=_LIMITATION_NOTICE if scan.status == "completed" else None,
        retry_after_seconds=3 if scan.status == "processing" else None,
        failure=(
            SkinScanFailure(code=scan.failure_code, retryable=scan.failure_retryable)
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
