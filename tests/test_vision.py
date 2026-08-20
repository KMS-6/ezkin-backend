"""Vision AI 이미지 분석(통합_기능_명세서.md `EZkin Vision AI Input` 5절) 검증.

실제 Anthropic API를 호출하지 않는다 — 키 미설정 시의 안전한 폴백은 직접 검증하고,
분석이 성공/품질 실패했다고 가정했을 때 `/skin-scans` 라우터가 결과를 올바르게
반영하는지는 monkeypatch로 검증한다.
"""

from types import SimpleNamespace

import anthropic
from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.modules.scans import router as scans_router
from app.modules.scans.vision import (
    VisionAnalysisResult,
    VisionOutcome,
    _build_outcome,
    analyze_image,
)

_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32


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
    # 테스트 환경엔 AAC_ANTHROPIC_API_KEY가 설정돼 있지 않다(tests/conftest.py 참고) —
    # 이 경우 네트워크 호출을 전혀 시도하지 않고 즉시 None을 반환해야 한다.
    result = await analyze_image(_JPEG_BYTES, "image/jpeg")

    assert result is None


async def test_analyze_image_returns_none_for_unsupported_media_type() -> None:
    # HEIC는 업로드는 허용되지만(5.2절) Claude Vision이 지원하지 않는 형식이라
    # 분석을 시도조차 하지 않는다.
    result = await analyze_image(_JPEG_BYTES, "image/heic")

    assert result is None


async def test_analyze_image_uses_anthropic_key_and_image_input(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeMessages:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(parsed_output=_result())

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.messages = FakeMessages()

        def with_options(self, **kwargs):
            captured["options"] = kwargs
            return self

    monkeypatch.setattr(settings, "anthropic_api_key", SecretStr("anthropic-test-key"))
    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)

    outcome = await analyze_image(_JPEG_BYTES, "image/jpeg")

    assert outcome is not None
    assert captured["api_key"] == "anthropic-test-key"
    assert captured["model"] == settings.vision_llm_model
    content = captured["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[1] == {"type": "text", "text": "이 사진을 분석해 주세요."}


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


def test_build_outcome_reports_first_quality_failure_in_table_order() -> None:
    # face_not_detected가 표에서 image_blurry보다 앞서므로, 둘 다 실패해도
    # face_not_detected만 사용자에게 안내한다.
    outcome = _build_outcome(_result(face_detected=False, image_blurry=True))

    assert outcome.failure_code == "face_not_detected"
    assert outcome.scores == {}


async def test_camera_scan_completes_when_vision_analysis_succeeds(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def fake_analyze(image_bytes: bytes, media_type: str) -> VisionOutcome:
        return VisionOutcome(
            scores={"redness": 0.4, "dryness": 0.2, "oiliness": 0.6},
            confidence={"redness": 0.8, "dryness": 0.8, "oiliness": 0.8},
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
    assert body["scores"] == {"redness": 0.4, "dryness": 0.2, "oiliness": 0.6}
    assert body["model"] == {
        "provider": "anthropic",
        "name": "claude-haiku-4-5",
        "version": "1",
    }
    assert body["failure"] is None


async def test_camera_scan_fails_with_specific_code_when_quality_gate_fails(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def fake_analyze(image_bytes: bytes, media_type: str) -> VisionOutcome:
        return VisionOutcome(failure_code="image_blurry", failure_message="다시 촬영해 주세요.")

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
