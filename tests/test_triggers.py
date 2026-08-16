import json

from httpx import AsyncClient

QUESTIONNAIRE_ANSWERS = json.dumps(
    [
        {"question_id": "redness", "value": "severe"},
        {"question_id": "tightness", "value": "mild"},
        {"question_id": "oiliness", "value": "none"},
    ]
)


async def test_pattern_analysis_requires_completed_scan(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    missing = await client.get(
        "/api/v1/pattern-analysis",
        headers=persona_headers,
        params={"scan_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert missing.status_code == 404

    malformed = await client.get(
        "/api/v1/pattern-analysis", headers=persona_headers, params={"scan_id": "not-a-uuid"}
    )
    assert malformed.status_code == 422

    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    camera_scan = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-camera-pattern"},
        data={"capture_method": "camera", "captured_at": "2026-08-16T09:00:00Z"},
        files={"image": ("scan.jpg", jpeg_bytes, "image/jpeg")},
    )
    scan_id = camera_scan.json()["scan_id"]

    not_completed = await client.get(
        "/api/v1/pattern-analysis", headers=persona_headers, params={"scan_id": scan_id}
    )
    assert not_completed.status_code == 409


async def test_pattern_analysis_for_completed_scan(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    scan = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-q-pattern"},
        data={
            "capture_method": "questionnaire",
            "captured_at": "2026-08-16T09:00:00Z",
            "questionnaire_version": "v1",
            "answers": QUESTIONNAIRE_ANSWERS,
        },
    )
    scan_id = scan.json()["scan_id"]

    response = await client.get(
        "/api/v1/pattern-analysis", headers=persona_headers, params={"scan_id": scan_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == scan_id
    assert body["common_knowledge"] is None
    assert body["observed_pattern"] is None


async def test_sos_urgent_message_returns_safety_reply(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    assert session.status_code == 201
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "숨쉬기 힘들어요"},
    )
    assert response.status_code == 200
    assert response.json()["reply_type"] == "safety"
    assert response.json()["expert_referral_suggested"] is True


async def test_sos_faq_match_and_unmatched_message(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    matched = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "요즘 피부가 건조하고 당겨요"},
    )
    assert matched.status_code == 200
    assert matched.json()["reply_type"] == "answer"
    assert matched.json()["matched_faq"]["faq_id"] == "faq_dryness"

    unmatched = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "완전히 관련 없는 이야기예요"},
    )
    assert unmatched.status_code == 501
