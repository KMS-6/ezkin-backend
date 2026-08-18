"""자연어 파서 단위 테스트 — 기능명세서_chatbot.md 6·7절, qa.md CHAT-NLU-* 기준.

DB가 필요 없는 순수 함수라 client fixture 없이 직접 검증한다.
"""

from app.modules.triggers.nlu import parse_message


# CHAT-NLU-001: 명확한 발화는 intent·entity가 정확히 추출되고 parse_confidence>=0.60이다.
def test_clear_product_usage_utterance_has_high_confidence() -> None:
    parsed = parse_message("오늘 레티놀 써도 돼?")

    assert parsed.intent == "product_usage"
    assert parsed.entities["ingredient_names"] == ["retinol"]
    assert parsed.entities["time"] == "today"
    assert parsed.parse_confidence >= 0.60


# CHAT-NLU-002: 애매한 발화는 parse_confidence<0.60이어야 한다(LLM escalation 대상,
# 지금은 LLM이 없어 결정적 fallback으로 처리된다).
def test_ambiguous_utterance_has_low_confidence() -> None:
    parsed = parse_message("그거 괜찮아?")

    assert parsed.parse_confidence < 0.60
    assert parsed.intent == "unknown"


def test_product_combination_extracts_both_ingredients() -> None:
    parsed = parse_message("비타민C랑 레티놀 같이 써도 돼?")

    assert parsed.intent == "product_combination"
    assert set(parsed.entities["ingredient_names"]) == {"retinol", "vitamin_c"}


def test_product_alternative_intent() -> None:
    parsed = parse_message("진정 제품 뭐 쓰지?")

    assert parsed.intent == "product_alternative"


def test_routine_order_intent_and_product_type() -> None:
    parsed = parse_message("토너 다음에 뭐 발라?")

    assert parsed.intent == "routine_order"
    assert parsed.entities["product_type"] == "toner"


def test_skin_trouble_extracts_body_area() -> None:
    parsed = parse_message("턱에 뭐가 났어")

    assert parsed.intent == "skin_trouble"
    assert parsed.entities["body_area"] == "chin"


def test_food_aftercare_extracts_food_type() -> None:
    parsed = parse_message("매운 거 먹었어")

    assert parsed.intent == "food_aftercare"
    assert parsed.entities["food_type"] == "spicy"


def test_skin_condition_extracts_symptom() -> None:
    parsed = parse_message("오늘 왜 이렇게 건조해?")

    assert parsed.intent == "skin_condition"
    assert "dryness" in parsed.entities["symptoms"]


def test_sunscreen_intent() -> None:
    parsed = parse_message("선크림 다시 발라야 해?")

    assert parsed.intent == "sunscreen"


def test_service_explanation_intent() -> None:
    parsed = parse_message("위험도 높음이 무슨 뜻이야?")

    assert parsed.intent == "service_explanation"


def test_unrelated_message_is_unknown_with_zero_confidence() -> None:
    parsed = parse_message("완전히 관련 없는 이야기예요")

    assert parsed.intent == "unknown"
    assert parsed.parse_confidence == 0.0


def test_product_name_entity_is_always_none() -> None:
    # PRODUCT_CATALOG 매칭은 MVP 범위 밖이라 product_name은 항상 None이어야 한다.
    parsed = parse_message("A사 레티놀 앰플 써도 돼?")

    assert parsed.entities["product_name"] is None
