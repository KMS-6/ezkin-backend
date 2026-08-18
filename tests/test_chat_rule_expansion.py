"""2~5단계 검증: FAQ intent 필터, 신규 규칙엔진 분기(product_alternative/sunscreen/
skin_trouble), 성분 상호작용 규칙 확장, 로깅 지표(compute_chat_metrics).
"""

import json

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers import logic
from tests.conftest import TEST_PERSONA_ID


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
    client: AsyncClient,
    headers: dict[str, str],
    brand: str,
    product_name: str,
    ingredient: str | None = None,
    product_type: str | None = None,
) -> str:
    data = {"brand": brand, "product_name": product_name}
    if ingredient is not None:
        data["ingredients_raw"] = json.dumps([ingredient])
    if product_type is not None:
        data["product_type"] = product_type
    response = await client.post("/api/v1/cosmetics", headers=headers, data=data)
    assert response.status_code == 201
    return response.json()["cosmetic_id"]


# --- 2단계: FAQ 매칭에 intent 필터 적용 ------------------------------------------------


def test_resolve_faq_intent_narrowing_prefers_matching_intent_over_higher_global_score(
    monkeypatch,
) -> None:
    entries = [
        {
            "faq_id": "faq_a",
            "version": 1,
            "label": "A",
            "intent": "skin_condition",
            "keywords": ["트러블케어"],
            "reply": "A",
        },
        {
            "faq_id": "faq_b",
            "version": 1,
            "label": "B",
            "intent": "routine_order",
            "keywords": ["트러블", "케어", "순서"],
            "reply": "B",
        },
    ]
    monkeypatch.setattr(logic, "FAQ_ENTRIES", entries)

    # intent 없이 검색하면 다중 키워드가 겹치는 faq_b 점수가 더 높아 그게 선택된다.
    unrestricted = logic.resolve_faq("트러블케어순서 알려줘")
    assert unrestricted["selected"]["faq_id"] == "faq_b"

    # intent=skin_condition으로 좁히면 faq_b는 후보에서 빠지고 faq_a가 선택된다.
    narrowed = logic.resolve_faq("트러블케어순서 알려줘", intent="skin_condition")
    assert narrowed["selected"]["faq_id"] == "faq_a"


def test_resolve_faq_falls_back_to_full_search_when_intent_has_no_candidates(
    monkeypatch,
) -> None:
    entries = [
        {
            "faq_id": "faq_a",
            "version": 1,
            "label": "A",
            "intent": "skin_condition",
            "keywords": ["건조"],
            "reply": "A",
        },
    ]
    monkeypatch.setattr(logic, "FAQ_ENTRIES", entries)

    # routine_order로 태그된 FAQ가 하나도 없으므로 전체 검색으로 되돌아간다.
    resolved = logic.resolve_faq("건조해요", intent="routine_order")
    assert resolved["selected"]["faq_id"] == "faq_a"


# --- 3단계: 규칙엔진을 나머지 intent로 확장 --------------------------------------------


async def test_product_alternative_recommends_owned_soothing_product(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    soothing_id = await _register_cosmetic(
        client, persona_headers, "B사", "병풀 진정 크림", ingredient="병풀"
    )
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "진정 제품 뭐 쓰지?")

    assert body["decision"] == {"rule_id": "rule_alternative_from_shelf", "code": "USE_PRODUCT"}
    assert body["referenced_cosmetic_ids"] == [soothing_id]
    assert "B사 병풀 진정 크림" in body["reply"]


async def test_product_alternative_without_owned_product_prompts_registration(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "진정 제품 뭐 쓰지?")

    assert body["decision"] is None
    assert body["referenced_cosmetic_ids"] == []


async def test_sunscreen_question_with_owned_product_mentions_it(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    sunscreen_id = await _register_cosmetic(
        client, persona_headers, "A사", "선크림", product_type="sunscreen"
    )
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "선크림 다시 발라야 해?")

    assert body["referenced_cosmetic_ids"] == [sunscreen_id]
    assert "A사 선크림" in body["reply"]


async def test_sunscreen_question_without_owned_product_gives_general_guidance(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "선크림 다시 발라야 해?")

    assert body["referenced_cosmetic_ids"] == []
    assert "2~3시간" in body["reply"]


async def test_skin_trouble_mentions_body_area_and_owned_soothing_product(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    soothing_id = await _register_cosmetic(
        client, persona_headers, "C사", "센텔라 앰플", ingredient="센텔라"
    )
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "이마에 뾰루지가 났어")

    assert "이마" in body["reply"]
    assert body["referenced_cosmetic_ids"] == [soothing_id]
    assert "today_risk_assessment" in body["used_contexts"]


# --- 4단계: 성분 상호작용 규칙 확장(레티놀+살리실산) ------------------------------------


async def test_retinol_salicylic_acid_combination_uses_avoid_same_routine_rule(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    retinol_id = await _register_cosmetic(
        client, persona_headers, "A사", "레티놀 앰플", ingredient="레티놀 2%"
    )
    bha_id = await _register_cosmetic(
        client, persona_headers, "D사", "살리실산 토너", ingredient="살리실산"
    )
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "레티놀이랑 살리실산 같이 써도 돼요?")

    assert body["decision"] == {
        "rule_id": "rule_retinol_salicylic_avoid",
        "code": "AVOID_SAME_ROUTINE",
    }
    assert set(body["referenced_cosmetic_ids"]) == {retinol_id, bha_id}


# --- 5단계: 로깅 — rule-only 처리율 등 운영 지표 ----------------------------------------


async def test_compute_chat_metrics_aggregates_fallback_and_confidence(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    session_id = await _create_session(client, persona_headers)
    await _send(client, persona_headers, session_id, "오늘 레티놀 써도 돼요?")
    await _send(client, persona_headers, session_id, "완전히 관련 없는 이야기예요")

    metrics = await logic.compute_chat_metrics(db_session, persona_id=TEST_PERSONA_ID)

    assert metrics["total_messages"] == 2
    assert metrics["rule_only_rate"] == 1.0
    assert metrics["fallback_rate"] == 0.5
    assert metrics["avg_parse_confidence"] is not None
    assert metrics["low_confidence_rate"] == 0.5


async def test_compute_chat_metrics_with_no_messages(db_session: AsyncSession) -> None:
    metrics = await logic.compute_chat_metrics(db_session, persona_id="no_such_persona")

    assert metrics == {
        "total_messages": 0,
        "rule_only_rate": 1.0,
        "fallback_rate": 0.0,
        "avg_parse_confidence": None,
        "low_confidence_rate": 0.0,
    }
