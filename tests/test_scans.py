import json
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SkinScan

QUESTIONNAIRE_ANSWERS = json.dumps(
    [
        {"question_id": "redness", "value": "severe"},
        {"question_id": "tightness", "value": "mild"},
        {"question_id": "oiliness", "value": "none"},
    ]
)


def _uniform_answers(value: str) -> str:
    return json.dumps(
        [
            {"question_id": "redness", "value": value},
            {"question_id": "tightness", "value": value},
            {"question_id": "oiliness", "value": value},
        ]
    )


async def test_questionnaire_scan_completes_with_scores(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-1"},
        data={
            "capture_method": "questionnaire",
            "captured_at": "2026-08-16T09:00:00Z",
            "questionnaire_version": "v1",
            "answers": QUESTIONNAIRE_ANSWERS,
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    scan_id = body["scan_id"]
    assert response.headers["Location"] == body["status_url"]

    result = await client.get(f"/api/v1/skin-scans/{scan_id}", headers=persona_headers)
    assert result.status_code == 200
    result_body = result.json()
    assert result_body["status"] == "completed"
    assert result_body["lower_accuracy"] is True
    assert result_body["scores"]["redness"] == 1.0
    assert result_body["scores"]["dryness"] == 0.33
    assert result_body["schema_version"] == "skin_observation.v1"
    assert result_body["confidence"] == {"redness": 0.5, "dryness": 0.5, "oiliness": 0.5}
    assert result_body["model"] == {"provider": "TBD", "name": "TBD", "version": "TBD"}
    assert result_body["retry_after_seconds"] is None
    # 최근 완료 스캔이 3건 미만이므로 기준선을 계산할 수 없다.
    assert result_body["delta_vs_baseline"] is None


async def test_delta_vs_baseline_uses_median_of_recent_scans(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    for index, value in enumerate(["none", "mild", "severe"]):
        response = await client.post(
            "/api/v1/skin-scans",
            headers={**persona_headers, "Idempotency-Key": f"baseline-hist-{index}"},
            data={
                "capture_method": "questionnaire",
                "captured_at": f"2026-08-1{index + 1}T09:00:00Z",
                "questionnaire_version": "v1",
                "answers": _uniform_answers(value),
            },
        )
        assert response.status_code == 202

    latest = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "baseline-latest"},
        data={
            "capture_method": "questionnaire",
            "captured_at": "2026-08-16T09:00:00Z",
            "questionnaire_version": "v1",
            "answers": _uniform_answers("moderate"),
        },
    )
    scan_id = latest.json()["scan_id"]

    result = await client.get(f"/api/v1/skin-scans/{scan_id}", headers=persona_headers)
    body = result.json()
    # median of [0.0, 0.33, 1.0] is 0.33; latest score is 0.66 -> delta 0.33
    assert body["delta_vs_baseline"] == {"redness": 0.33, "dryness": 0.33, "oiliness": 0.33}


async def test_processing_scan_returns_retry_after_seconds(
    client: AsyncClient, db_session: AsyncSession, persona_headers: dict[str, str]
) -> None:
    scan = SkinScan(
        persona_id="persona_001",
        capture_method="camera",
        captured_at=datetime(2026, 8, 16, 9, 0, tzinfo=UTC),
        status="processing",
    )
    db_session.add(scan)
    await db_session.commit()

    result = await client.get(f"/api/v1/skin-scans/{scan.id}", headers=persona_headers)
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "processing"
    assert body["retry_after_seconds"] == 3
    assert body["schema_version"] is None
    assert body["model"] is None
    assert body["confidence"] is None


async def test_idempotency_key_replays_same_scan(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    headers = {**persona_headers, "Idempotency-Key": "idem-shared"}
    payload = {
        "capture_method": "questionnaire",
        "captured_at": "2026-08-16T09:00:00Z",
        "questionnaire_version": "v1",
        "answers": QUESTIONNAIRE_ANSWERS,
    }
    first = await client.post("/api/v1/skin-scans", headers=headers, data=payload)
    second = await client.post("/api/v1/skin-scans", headers=headers, data=payload)
    assert first.json()["scan_id"] == second.json()["scan_id"]

    conflicting = await client.post(
        "/api/v1/skin-scans",
        headers=headers,
        data={**payload, "captured_at": "2026-08-16T10:00:00Z"},
    )
    assert conflicting.status_code == 409


async def test_camera_scan_resolves_to_model_not_implemented(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-camera"},
        data={"capture_method": "camera", "captured_at": "2026-08-16T09:00:00Z"},
        files={"image": ("scan.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 202
    scan_id = response.json()["scan_id"]

    result = await client.get(f"/api/v1/skin-scans/{scan_id}", headers=persona_headers)
    body = result.json()
    assert body["status"] == "failed"
    assert body["failure"]["code"] == "model_not_implemented"
    assert body["failure"]["retryable"] is False


async def test_questionnaire_missing_required_question_is_rejected(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-invalid"},
        data={
            "capture_method": "questionnaire",
            "captured_at": "2026-08-16T09:00:00Z",
            "questionnaire_version": "v1",
            "answers": json.dumps([{"question_id": "redness", "value": "mild"}]),
        },
    )
    assert response.status_code == 422


async def test_scan_owned_by_other_persona_is_not_found(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/skin-scans/00000000-0000-0000-0000-000000000000",
        headers={"X-Mock-Persona-Id": "persona_001"},
    )
    assert response.status_code == 404
