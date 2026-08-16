import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from httpx import AsyncClient

KST = ZoneInfo("Asia/Seoul")

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
    assert unmatched.status_code == 200
    assert unmatched.json()["reply_type"] == "clarification"
    assert unmatched.json()["matched_faq"] is None


async def test_sos_self_harm_message_returns_crisis_reply(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "너무 힘들어서 자해하고 싶어요"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply_type"] == "safety"
    assert body["safety_flag"] == "self_harm"
    assert body["expert_referral_suggested"] is True
    assert body["referenced_cosmetic_ids"] == []


async def test_sos_supplement_question_is_out_of_scope(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "유산균 얼마나 먹어야 해요?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply_type"] == "out_of_scope"
    assert body["matched_faq"] is None
    assert body["expert_referral_suggested"] is False


async def test_sos_message_validation_rejects_blank_and_oversized_input(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    blank = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "   "},
    )
    assert blank.status_code == 422

    control_chars_only = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "\x00\x01"},
    )
    assert control_chars_only.status_code == 422

    too_long = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "가" * 1001},
    )
    assert too_long.status_code == 422


async def test_sos_message_rejects_unregistered_mock_persona(client: AsyncClient) -> None:
    other_headers = {"X-Mock-Persona-Id": "unknown_persona"}
    response = await client.post("/api/v1/sos/sessions", headers=other_headers)
    assert response.status_code == 400


async def _register_cosmetic(
    client: AsyncClient, headers: dict[str, str], brand: str, product_name: str, ingredient: str
) -> str:
    response = await client.post(
        "/api/v1/cosmetics",
        headers=headers,
        data={
            "brand": brand,
            "product_name": product_name,
            "ingredients_raw": json.dumps([ingredient]),
        },
    )
    assert response.status_code == 201
    return response.json()["cosmetic_id"]


async def test_sos_retinol_question_is_personalized_by_risk_and_my_shelf(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    retinol_id = await _register_cosmetic(
        client, persona_headers, "A사", "레티놀 앰플", "레티놀 2%"
    )
    soothing_id = await _register_cosmetic(
        client, persona_headers, "B사", "세라마이드 크림", "세라마이드"
    )

    today = datetime.now(KST).date().isoformat()
    metric_response = await client.post(
        "/api/v1/daily-metrics/manual",
        headers=persona_headers,
        json={"metric_date": today, "diet_flag": "spicy"},
    )
    assert metric_response.status_code == 200

    scan_response = await client.post(
        "/api/v1/skin-scans",
        headers={**persona_headers, "Idempotency-Key": "idem-sos-retinol"},
        data={
            "capture_method": "questionnaire",
            "captured_at": datetime.now(UTC).isoformat(),
            "questionnaire_version": "v1",
            "answers": json.dumps(
                [
                    {"question_id": "redness", "value": "severe"},
                    {"question_id": "tightness", "value": "mild"},
                    {"question_id": "oiliness", "value": "mild"},
                ]
            ),
        },
    )
    assert scan_response.status_code == 202

    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "오늘 레티놀 써도 돼요?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply_type"] == "answer"
    assert body["matched_faq"]["faq_id"] == "faq_retinol_today"
    assert body["decision"] == {"rule_id": "rule_retinol_high_risk", "code": "SKIP_PRODUCT"}
    assert set(body["referenced_cosmetic_ids"]) == {retinol_id, soothing_id}
    assert "today_risk_assessment" in body["used_contexts"]
    assert "owned_products" in body["used_contexts"]
    assert body["reply"].count("A사 레티놀 앰플") == 1
    assert "B사 세라마이드 크림" in body["reply"]


async def test_sos_retinol_question_without_owned_product_offers_general_guidance(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "레티놀 써도 돼요?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] is None
    assert body["referenced_cosmetic_ids"] == []


async def test_sos_retinol_vitamin_c_combination_uses_avoid_same_routine_rule(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    retinol_id = await _register_cosmetic(
        client, persona_headers, "A사", "레티놀 앰플", "레티놀 2%"
    )
    vitamin_c_id = await _register_cosmetic(
        client, persona_headers, "C사", "비타민C 앰플", "비타민C 15%"
    )

    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "비타민C랑 레티놀 같이 써도 돼요?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == {
        "rule_id": "rule_retinol_vitaminc_avoid",
        "code": "AVOID_SAME_ROUTINE",
    }
    assert set(body["referenced_cosmetic_ids"]) == {retinol_id, vitamin_c_id}
