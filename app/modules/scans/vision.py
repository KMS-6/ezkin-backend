"""Vision AI 이미지 분석 — 통합_기능_명세서.md `EZkin Vision AI Input` 5절.

멀티모달 LLM에 구조화 출력(JSON schema)을 강제해 관찰값을 받고, 그 값을 서버 코드가
검증·필터링한다 — 2절 제외 범위("LLM의 독자적 수치 계산 또는 제품명 생성 금지")에
맞춰 품질 통과 여부와 confidence 임계값 판정은 LLM이 아니라 이 모듈이 최종 결정한다.

API 키가 없거나 SDK가 없거나 지원하지 않는 이미지 형식이면 None을 반환한다. 일시적인
호출 실패와 타임아웃은 재시도 가능한 실패 결과로 구분한다.

응답 계약(`failure_code`)은 항상 `model_not_implemented`로 뭉뚱그려지지만, 실제 원인
(키 누락/인증 실패/모델 미지원/요청 형식 오류/일시적 API 장애)은 아래에서 서버 로그로
구분해 남긴다 — 프론트 API 계약을 바꾸지 않으면서 운영 중 원인 파악을 돕기 위함.
"""

import base64
import logging

from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_TIMEOUT_SECONDS = 20.0
ANALYSIS_MAX_TOKENS = 500
VISION_PROVIDER = "openai"
VISION_MODEL_VERSION = "1"
VISION_SCHEMA_VERSION = "skin_observation.v1"

# 5.4절: 신뢰도가 기준 미만인 지표는 결과에서 제외한다. 임계값은 스펙 5.3절에서도
# "확인 필요"로 남아 있는 미확정 값이라, questionnaire 경로의 기본 confidence(0.5,
# scans/router.py)와 같은 값을 잠정 기준으로 쓴다.
CONFIDENCE_THRESHOLD = 0.5

# OpenAI Vision이 지원하는 형식만 분석을 시도한다. HEIC는 업로드는 허용되지만(5.2절)
# 이 경로에서는 분석 불가로 취급해 model_not_implemented로 폴백시킨다.
_SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png"}
_TRANSIENT_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 529}

# 5.3절 품질 검사 표 순서. 여러 항목이 동시에 실패해도 표 순서상 첫 실패만 사용자에게
# 안내한다(재촬영 가이드를 한 번에 하나씩만 보여주기 위함).
# invalid_face_pose·face_occluded는 완화 대상: 관찰 신뢰도에 영향은 있으나 하드 게이트로
# 막을 만큼 치명적이지 않다고 보고 치명 실패에서 제외했다(유효 스캔 축적 속도 우선).
_QUALITY_FAILURES: tuple[tuple[str, str, str], ...] = (
    ("face_not_detected", "face_not_detected", "화면에 얼굴이 잘 보이도록 맞춰 주세요."),
    ("multiple_faces", "multiple_faces", "화면에 한 명의 얼굴만 나오도록 맞춰 주세요."),
    ("lighting_too_dark", "lighting_too_dark", "조명을 밝게 하고 다시 촬영해 주세요."),
    ("lighting_too_bright", "lighting_too_bright", "직사광선을 피하고 다시 촬영해 주세요."),
    ("image_blurry", "image_blurry", "렌즈를 닦고 기기를 고정한 뒤 다시 촬영해 주세요."),
)

_SYSTEM_PROMPT = (
    "당신은 피부과 진료가 아닌 비의료적 관찰 목적의 피부 상태 분석 보조입니다. "
    "제공된 얼굴 사진을 보고 아래 스키마에 맞춰서만 응답하세요.\n\n"
    "먼저 사진 품질을 판정하세요: 얼굴이 정확히 1개 검출되는지, 조명이 적절한지, "
    "선명한지, 정면 자세인지, 가림 없이 촬영됐는지.\n\n"
    "품질에 문제가 없다면 홍조(redness), 건조함(dryness), 유분(oiliness) 세 가지를 "
    "0(관찰되지 않음)~1(강하게 관찰됨) 사이의 상대적 강도로 평가하고, 각 판단에 대한 "
    "confidence(0~1)도 함께 제시하세요.\n\n"
    "절대로 질환명, 원인, 치료 필요성을 언급하거나 의료적 진단을 내리지 마세요 — "
    "이 결과는 상대적 관찰값일 뿐입니다."
)


class VisionAnalysisResult(BaseModel):
    face_detected: bool
    multiple_faces: bool
    lighting_too_dark: bool
    lighting_too_bright: bool
    image_blurry: bool
    invalid_face_pose: bool
    face_occluded: bool
    redness_score: float = Field(ge=0, le=1)
    redness_confidence: float = Field(ge=0, le=1)
    dryness_score: float = Field(ge=0, le=1)
    dryness_confidence: float = Field(ge=0, le=1)
    oiliness_score: float = Field(ge=0, le=1)
    oiliness_confidence: float = Field(ge=0, le=1)


class VisionOutcome(BaseModel):
    """호출부가 바로 소비하는 정리된 결과. `failure_code`가 있으면 품질 게이트
    실패이고, 없으면 `scores`/`confidence`가 채워진 성공이다."""

    failure_code: str | None = None
    failure_message: str | None = None
    failure_retryable: bool = False
    scores: dict[str, float] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    model_provider: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    schema_version: str | None = None


def _quality_failure(result: VisionAnalysisResult) -> tuple[str, str] | None:
    flags = {
        "face_not_detected": not result.face_detected,
        "multiple_faces": result.multiple_faces,
        "lighting_too_dark": result.lighting_too_dark,
        "lighting_too_bright": result.lighting_too_bright,
        "image_blurry": result.image_blurry,
    }
    for flag_name, code, message in _QUALITY_FAILURES:
        if flags[flag_name]:
            return code, message
    return None


def _build_outcome(result: VisionAnalysisResult) -> VisionOutcome:
    failure = _quality_failure(result)
    if failure is not None:
        code, message = failure
        return VisionOutcome(
            failure_code=code,
            failure_message=message,
            failure_retryable=True,
        )

    raw = {
        "redness": (result.redness_score, result.redness_confidence),
        "dryness": (result.dryness_score, result.dryness_confidence),
        "oiliness": (result.oiliness_score, result.oiliness_confidence),
    }
    kept = {metric: pair for metric, pair in raw.items() if pair[1] >= CONFIDENCE_THRESHOLD}
    if not kept:
        return VisionOutcome(
            failure_code="insufficient_confidence",
            failure_message="분석 신뢰도가 충분하지 않습니다. 다시 촬영해 주세요.",
            failure_retryable=True,
        )
    return VisionOutcome(
        scores={metric: round(score, 2) for metric, (score, _) in kept.items()},
        confidence={metric: round(confidence, 2) for metric, (_, confidence) in kept.items()},
    )


async def analyze_image(image_bytes: bytes, media_type: str) -> VisionOutcome | None:
    """이미지를 분석해 품질 게이트 결과 또는 관찰값을 반환한다.

    분석 자체를 시도할 수 없으면(키 없음·SDK 없음·미지원 형식) None을 반환한다.
    모델 타임아웃과 일시적 호출 실패는 재시도 가능한 실패 결과로 반환한다.
    """
    api_key = settings.openai_api_key
    if api_key is None:
        logger.warning("Vision 분석 건너뜀: AAC_OPENAI_API_KEY가 설정되지 않았습니다.")
        return None
    if media_type not in _SUPPORTED_MEDIA_TYPES:
        return None

    try:
        import openai
    except ImportError:
        logger.error("Vision 분석 건너뜀: openai 패키지가 설치되지 않았습니다.")
        return None

    encoded_image = base64.b64encode(image_bytes).decode("ascii")

    try:
        client = openai.AsyncOpenAI(api_key=api_key.get_secret_value())
        response = await client.with_options(
            timeout=ANALYSIS_TIMEOUT_SECONDS
        ).chat.completions.parse(
            model=settings.vision_llm_model,
            max_completion_tokens=ANALYSIS_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{encoded_image}"},
                        },
                        {"type": "text", "text": "이 사진을 분석해 주세요."},
                    ],
                },
            ],
            response_format=VisionAnalysisResult,
        )
    except openai.APITimeoutError:
        logger.warning("Vision 분석 실패: OpenAI API 타임아웃(일시적).")
        return VisionOutcome(
            failure_code="analysis_timeout",
            failure_message="분석 시간이 초과되었습니다.",
            failure_retryable=True,
        )
    except openai.APIConnectionError:
        logger.warning("Vision 분석 실패: OpenAI API 연결 오류(일시적).")
        return VisionOutcome(
            failure_code="analysis_failed",
            failure_message="분석을 완료하지 못했습니다.",
            failure_retryable=True,
        )
    except openai.APIStatusError as exc:
        if exc.status_code in _TRANSIENT_STATUS_CODES:
            logger.warning("Vision 분석 실패: OpenAI API 일시적 장애(status=%s).", exc.status_code)
            return VisionOutcome(
                failure_code="analysis_failed",
                failure_message="분석을 완료하지 못했습니다.",
                failure_retryable=True,
            )
        if exc.status_code == 401:
            logger.error("Vision 분석 실패: 인증 실패(401) — AAC_OPENAI_API_KEY 값을 확인하세요.")
        elif exc.status_code == 403:
            logger.error("Vision 분석 실패: 권한 거부(403) — API 키 권한/조직 설정을 확인하세요.")
        elif exc.status_code == 404:
            logger.error(
                "Vision 분석 실패: 모델 미지원(404, model=%s) — "
                "AAC_VISION_LLM_MODEL 값을 확인하세요.",
                settings.vision_llm_model,
            )
        elif exc.status_code == 400:
            logger.error("Vision 분석 실패: 요청 형식 오류(400) — %s", exc.message)
        else:
            logger.error(
                "Vision 분석 실패: 처리되지 않은 API 오류(status=%s) — %s",
                exc.status_code,
                exc.message,
            )
        return None
    except Exception:
        logger.exception("Vision 분석 실패: 예상하지 못한 예외.")
        return None

    result = response.choices[0].message.parsed
    if result is None:
        return VisionOutcome(
            failure_code="analysis_failed",
            failure_message="분석을 완료하지 못했습니다.",
            failure_retryable=True,
        )
    outcome = _build_outcome(result)
    if outcome.failure_code is not None:
        return outcome
    return outcome.model_copy(
        update={
            "model_provider": VISION_PROVIDER,
            "model_name": settings.vision_llm_model,
            "model_version": VISION_MODEL_VERSION,
            "schema_version": VISION_SCHEMA_VERSION,
        }
    )
