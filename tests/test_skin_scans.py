import json

from httpx import AsyncClient

QUESTIONNAIRE_ANSWERS = json.dumps(
    [
        {"question_id": "redness", "value": "severe"},
        {"question_id": "tightness", "value": "mild"},
        {"question_id": "oiliness", "value": "none"},
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
