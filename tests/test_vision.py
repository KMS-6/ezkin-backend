"""Vision AI 이미지 분석(통합_기능_명세서.md `EZkin Vision AI Input` 5절) 검증.

실제 OpenAI API를 호출하지 않는다 — 키 미설정 시의 안전한 폴백은 직접 검증하고,
분석이 성공/품질 실패했다고 가정했을 때 `/skin-scans` 라우터가 결과를 올바르게
반영하는지는 monkeypatch로 검증한다.
"""

import base64
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import httpx2
import openai
import pytest
from httpx import AsyncClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import read_and_validate_image
from app.models.scan import SkinScan
from app.modules.scans import router as scans_router
from app.modules.scans.vision import (
    VisionAnalysisResult,
    VisionOutcome,
    _build_outcome,
    analyze_image,
)


def _jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (2, 2), "white")
    exif = Image.Exif()
    exif[0x010F] = "private-device"
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


_JPEG_BYTES = _jpeg_with_exif()
_ENCODED_JPEG = base64.b64encode(_JPEG_BYTES).decode("ascii")


def _result(**overrides: object) -> VisionAnalysisResult:
    defaults: dict[str, object] = {
        "face_detected": True,
        "multiple_faces": False,
        "lighting_too_dark": False,
        "lighting_too_bright": False,
        "image_blurry": False,
        "invalid_face_pose": False,
        "face_occluded": False,
        "redness_score": 0.4,
        "redness_confidence": 0.8,
        "dryness_score": 0.2,
        "dryness_confidence": 0.8,
        "oiliness_score": 0.6,
        "oiliness_confidence": 0.8,
    }
    defaults.update(overrides)
    return VisionAnalysisResult(**defaults)


async def test_analyze_image_returns_none_without_api_key() -> None:
    # 테스트 환경엔 AAC_OPENAI_API_KEY가 설정돼 있지 않다(tests/conftest.py 참고) —
    # 이 경우 네트워크 호출을 전혀 시도하지 않고 즉시 None을 반환해야 한다.
    result = await analyze_image(_JPEG_BYTES, "image/jpeg")

    assert result is None


async def test_analyze_image_returns_none_for_unsupported_media_type() -> None:
    # HEIC는 업로드는 허용되지만(5.2절) OpenAI Vision이 지원하지 않는 형식이라
    # 분석을 시도조차 하지 않는다.
    result = await analyze_image(_JPEG_BYTES, "image/heic")

    assert result is None


async def test_analyze_image_uses_openai_key_and_image_input(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(parsed=_result())
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.chat = FakeChat()

        def with_options(self, **kwargs):
            captured["options"] = kwargs
            return self

    monkeypatch.setattr(settings, "openai_api_key", SecretStr("openai-test-key"))
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)

    outcome = await analyze_image(_JPEG_BYTES, "image/jpeg")

    assert outcome is not None
    assert captured["api_key"] == "openai-test-key"
    assert captured["model"] == settings.vision_llm_model
    assert captured["messages"][0]["role"] == "system"
    content = captured["messages"][1]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"] == f"data:image/jpeg;base64,{_ENCODED_JPEG}"
    assert content[1] == {"type": "text", "text": "이 사진을 분석해 주세요."}


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_retryable"),
    [
        (
            openai.APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com")),
            "analysis_timeout",
            True,
        ),
        (
            openai.APIConnectionError(request=httpx2.Request("POST", "https://api.openai.com")),
            "analysis_failed",
            True,
        ),
        (
            openai.RateLimitError(
                "rate limited",
                response=httpx2.Response(
                    429,
                    request=httpx2.Request("POST", "https://api.openai.com"),
                ),
                body=None,
            ),
            "analysis_failed",
            True,
        ),
    ],
)
async def test_analyze_image_classifies_retryable_provider_failures(
    error: Exception,
    expected_code: str,
    expected_retryable: bool,
    monkeypatch,
) -> None:
    class FakeCompletions:
        async def parse(self, **kwargs):
            raise error

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

        def with_options(self, **kwargs):
            return self

    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: FakeClient())

    outcome = await analyze_image(_JPEG_BYTES, "image/jpeg")

    assert outcome is not None
    assert outcome.failure_code == expected_code
    assert outcome.failure_retryable is expected_retryable


@pytest.mark.parametrize(
    "error",
    [
        openai.AuthenticationError(
            "invalid key",
            response=httpx2.Response(
                401,
                request=httpx2.Request("POST", "https://api.openai.com"),
            ),
            body=None,
        ),
        RuntimeError("unexpected failure"),
    ],
)
async def test_analyze_image_returns_none_for_non_retryable_provider_failures(
    error: Exception, monkeypatch
) -> None:
    class FakeCompletions:
        async def parse(self, **kwargs):
            raise error

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

        def with_options(self, **kwargs):
            return self

    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: FakeClient())

    assert await analyze_image(_JPEG_BYTES, "image/jpeg") is None


def test_build_outcome_returns_scores_when_quality_passes() -> None:
    outcome = _build_outcome(_result())

    assert outcome.failure_code is None
    assert outcome.scores == {"redness": 0.4, "dryness": 0.2, "oiliness": 0.6}
    assert outcome.confidence == {"redness": 0.8, "dryness": 0.8, "oiliness": 0.8}


def test_build_outcome_drops_low_confidence_metric() -> None:
    outcome = _build_outcome(_result(oiliness_confidence=0.3))

    assert outcome.failure_code is None
    assert set(outcome.scores) == {"redness", "dryness"}
    assert "oiliness" not in outcome.confidence


def test_build_outcome_fails_when_every_metric_has_low_confidence() -> None:
    outcome = _build_outcome(
        _result(
            redness_confidence=0.1,
            dryness_confidence=0.2,
            oiliness_confidence=0.3,
        )
    )

    assert outcome.failure_code == "insufficient_confidence"
    assert outcome.failure_retryable is True
    assert outcome.scores == {}


def test_build_outcome_reports_first_quality_failure_in_table_order() -> None:
    # face_not_detected가 표에서 image_blurry보다 앞서므로, 둘 다 실패해도
    # face_not_detected만 사용자에게 안내한다.
    outcome = _build_outcome(_result(face_detected=False, image_blurry=True))

    assert outcome.failure_code == "face_not_detected"
    assert outcome.failure_retryable is True
    assert outcome.scores == {}


async def test_camera_scan_completes_when_vision_analysis_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    persona_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_analyze(image_bytes: bytes, media_type: str) -> VisionOutcome:
        return VisionOutcome(
            scores={"redness": 0.4, "dryness": 0.2, "oiliness": 0.6},
            confidence={"redness": 0.8, "dryness": 0.8, "oiliness": 0.8},
            model_provider="openai",
            model_name="gpt-5.4-mini",
            model_version="1",
            schema_version="skin_observation.v1",
        )

    monkeypatch.setattr(scans_router, "analyze_image", fake_analyze)

    response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-vision-ok"},
        data={"capture_method": "camera", "captured_at": "2026-08-16T09:00:00Z"},
        files={"image": ("scan.jpg", _JPEG_BYTES, "image/jpeg")},
    )
    scan_id = response.json()["scan_id"]

    result = await client.get(f"/api/v1/skin-scans/{scan_id}", headers=persona_headers)
    body = result.json()
    assert body["status"] == "completed"
    assert body["lower_accuracy"] is False
    assert body["scores"] == {"redness": 0.4, "dryness": 0.2, "oiliness": 0.6}
    assert body["model"] == {
        "provider": "openai",
        "name": "gpt-5.4-mini",
        "version": "1",
    }
    assert body["failure"] is None

    scan = await db_session.get(SkinScan, UUID(scan_id))
    assert scan is not None
    assert scan.image_storage_key is None
    assert scan.model_name == "gpt-5.4-mini"

    monkeypatch.setattr(settings, "vision_llm_model", "replacement-model")
    repeated = await client.get(f"/api/v1/skin-scans/{scan_id}", headers=persona_headers)
    assert repeated.json()["model"]["name"] == "gpt-5.4-mini"


async def test_camera_scan_fails_with_specific_code_when_quality_gate_fails(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def fake_analyze(image_bytes: bytes, media_type: str) -> VisionOutcome:
        return VisionOutcome(
            failure_code="image_blurry",
            failure_message="다시 촬영해 주세요.",
            failure_retryable=True,
        )

    monkeypatch.setattr(scans_router, "analyze_image", fake_analyze)

    response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-vision-blurry"},
        data={"capture_method": "camera", "captured_at": "2026-08-16T09:00:00Z"},
        files={"image": ("scan.jpg", _JPEG_BYTES, "image/jpeg")},
    )
    scan_id = response.json()["scan_id"]

    result = await client.get(f"/api/v1/skin-scans/{scan_id}", headers=persona_headers)
    body = result.json()
    assert body["status"] == "failed"
    assert body["failure"]["code"] == "image_blurry"
    # 품질 게이트 실패는 model_not_implemented와 달리 재촬영하면 성공할 수 있다.
    assert body["failure"]["retryable"] is True


async def test_camera_scan_preserves_retryable_analysis_failure(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def fake_analyze(image_bytes: bytes, media_type: str) -> VisionOutcome:
        return VisionOutcome(
            failure_code="analysis_timeout",
            failure_message="분석 시간이 초과되었습니다.",
            failure_retryable=True,
        )

    monkeypatch.setattr(scans_router, "analyze_image", fake_analyze)

    response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-vision-timeout"},
        data={"capture_method": "camera", "captured_at": "2026-08-16T09:00:00Z"},
        files={"image": ("scan.jpg", _JPEG_BYTES, "image/jpeg")},
    )
    result = await client.get(
        f"/api/v1/skin-scans/{response.json()['scan_id']}", headers=persona_headers
    )

    assert result.json()["failure"] == {
        "code": "analysis_timeout",
        "retryable": True,
    }


async def test_read_and_validate_image_removes_exif() -> None:
    from starlette.datastructures import Headers, UploadFile

    upload = UploadFile(
        filename="scan.jpg",
        file=BytesIO(_jpeg_with_exif()),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    sanitized = await read_and_validate_image(upload)

    with Image.open(BytesIO(sanitized)) as image:
        assert image.getexif() == {}
