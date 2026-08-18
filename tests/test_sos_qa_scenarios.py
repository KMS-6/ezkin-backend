"""qa.md의 챗봇 관련 TC(CHAT-NLU/CHAT-RULE/CHAT-SAFE/SUPP)를 기준으로 한 추가 검증.

각 테스트 상단 주석의 TC ID는 docs/tmp/qa.md 9~13절과 대응된다.
"""

import json

from httpx import AsyncClient


async def _create_session(client: AsyncClient, headers: dict[str, str]) -> str:
    session = await client.post("/api/v1/sos/sessions", headers=headers)
    assert session.status_code == 201
    return session.json()["session_id"]


async def _send(client: AsyncClient, headers: dict[str, str], session_id: str, message: str):
    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=headers,
        json={"message": message},
    )
    assert response.status_code == 200
    return response.json()


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


# CHAT-NLU-008: 위험 키워드는 FAQ 매칭보다 먼저 검사되어 고정 안전 답변이 우선 반환된다.
async def test_urgent_keyword_takes_priority_over_faq_match(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "숨쉬기 힘든데 트러블 케어법 알려줘")

    assert body["reply_type"] == "safety"
    assert body["safety_flag"] == "urgent_symptom"
    assert body["matched_faq"] is None
    assert "케어" not in body["reply"]


# CHAT-RULE-003: 검증된 상호작용 규칙이 없는 성분 조합은 "함께 사용해도 안전하다"고 단정하지
# 않는다. 레티놀·비타민C 조합(승인된 규칙)이 아닌 임의 조합에 대한 확인.
async def test_unverified_ingredient_combo_does_not_assert_safety(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)
    body = await _send(
        client, persona_headers, session_id, "나이아신아마이드랑 살리실산 같이 써도 돼요?"
    )

    assert body["decision"] is None
    forbidden_claims = ("함께 사용해도 안전", "같이 써도 안전", "동시에 사용해도 안전")
    assert not any(claim in body["reply"] for claim in forbidden_claims)


# CHAT-RULE-006: 삭제된 화장품은 신규 답변에서 보유 제품으로 취급하지 않는다.
async def test_deleted_cosmetic_is_excluded_from_personalization(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    retinol_id = await _register_cosmetic(
        client, persona_headers, "A사", "레티놀 앰플", "레티놀 2%"
    )
    delete_response = await client.delete(
        f"/api/v1/cosmetics/{retinol_id}", headers=persona_headers
    )
    assert delete_response.status_code == 204

    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "레티놀 써도 돼요?")

    assert body["decision"] is None
    assert body["referenced_cosmetic_ids"] == []
    assert "A사 레티놀 앰플" not in body["reply"]


# CHAT-RULE-004 연장: 위험 요인이 없는 날에는 보유 레티놀 제품을 평소대로 사용해도 된다고
# 안내한다(동일 FAQ라도 위험도에 따라 결과가 달라짐 — CB-05).
async def test_retinol_question_with_normal_risk_allows_usual_use(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    retinol_id = await _register_cosmetic(
        client, persona_headers, "A사", "레티놀 앰플", "레티놀 2%"
    )
    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "레티놀 써도 돼요?")

    assert body["decision"] == {"rule_id": "rule_retinol_normal_risk", "code": "USE_PRODUCT"}
    assert body["referenced_cosmetic_ids"] == [retinol_id]


# SUPP-010: "비타민 먹으면 피지 조절되나요?" 처럼 SUPPLEMENT_KEYWORDS에 없는 구어체 표현도
# out_of_scope로 분류되고 예방 효과를 단정하지 않아야 한다.
async def test_oral_vitamin_question_is_out_of_scope(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "비타민 먹으면 피지 조절되나요?")

    assert body["reply_type"] == "out_of_scope"
    forbidden_claims = ("조절됩니다", "예방됩니다", "효과가 있습니다")
    assert not any(claim in body["reply"] for claim in forbidden_claims)


# 비타민C를 도포하는(먹지 않는) 스킨케어 질문은 out_of_scope로 오분류되면 안 된다.
async def test_topical_vitamin_c_question_is_not_out_of_scope(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "비타민C 세럼 발라도 돼요?")

    assert body["reply_type"] != "out_of_scope"


# CHAT-SAFE-004: 처방약 시작·중단 안내는 거부하고 전문가 상담으로 유도해야 한다.
async def test_medication_discontinuation_question_is_redirected_to_expert(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "이 약 오늘부터 끊어도 돼요?")

    assert body["reply_type"] == "out_of_scope"
    assert body["expert_referral_suggested"] is True
    forbidden_claims = ("끊으세요", "중단하세요", "끊어도 됩니다")
    assert not any(claim in body["reply"] for claim in forbidden_claims)


# SUPP-004: 야식 뒤 영양제를 새로 사자는 질문도 out_of_scope로 처리하고, 야식 FAQ로
# 새어나가 특정 케어를 권하지 않아야 한다.
async def test_supplement_purchase_after_food_stays_out_of_scope(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)
    body = await _send(
        client, persona_headers, session_id, "매운 거 먹었으니까 유산균 새로 사서 먹을까요?"
    )

    assert body["reply_type"] == "out_of_scope"


# CB-11 / 페르소나 데이터 격리: 존재하지 않는 세션 ID로 접근하면 404.
async def test_message_to_unknown_session_returns_404(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/sos/sessions/00000000-0000-0000-0000-000000000000/messages",
        headers=persona_headers,
        json={"message": "안녕하세요"},
    )
    assert response.status_code == 404
