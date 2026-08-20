"""6단계 검증: 저신뢰도 파싱 LLM escalation(기능명세서_chatbot.md 10.2절 4단계).

실제 Anthropic API를 호출하지 않는다 — 키 미설정 시의 안전한 폴백과, escalate_parse가
성공했다고 가정했을 때 build_chat_reply/compute_chat_metrics가 그 결과를 올바르게
반영하는지를 monkeypatch로 검증한다.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sos import SosMessage
from app.modules.triggers import llm_escalation, logic
from app.modules.triggers.nlu import ParsedMessage
from tests.conftest import TEST_PERSONA_ID
from tests.test_chat_rule_expansion import _create_session, _send

_EMPTY_ENTITIES = {
    "product_name": None,
    "ingredient_names": [],
    "product_type": None,
    "body_area": None,
    "symptoms": [],
    "food_type": None,
    "time": None,
}


async def test_escalate_parse_returns_none_without_api_key() -> None:
    # 테스트 환경엔 AAC_ANTHROPIC_API_KEY가 설정돼 있지 않다(tests/conftest.py 참고) —
    # 이 경우 네트워크 호출을 전혀 시도하지 않고 즉시 None을 반환해야 한다.
    result = await llm_escalation.escalate_parse("아무 메시지")

    assert result is None


async def test_low_confidence_message_uses_escalated_intent_and_entities(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def fake_escalate(message: str, persona_context: str | None = None) -> ParsedMessage:
        return ParsedMessage(
            intent="skin_trouble",
            entities={**_EMPTY_ENTITIES, "body_area": "chin"},
            risk_terms=[],
            normalized_query=message,
            parse_confidence=0.75,
        )

    monkeypatch.setattr(logic, "escalate_parse", fake_escalate)
    session_id = await _create_session(client, persona_headers)

    # 규칙 기반 파서로는 intent=unknown, parse_confidence=0.0이라 escalation 대상이다.
    body = await _send(client, persona_headers, session_id, "그거 왜그럴까")

    assert "턱" in body["reply"]


def test_validate_llm_result_drops_out_of_vocabulary_body_area() -> None:
    # LLM이 정규화 ID(BODY_AREA_ALIASES 키) 대신 자유 텍스트를 반환하면 서버가 그 값을
    # 버리고 None으로 되돌려야 한다 — 그렇지 않으면 skin_trouble 분기의
    # BODY_AREA_ALIASES[body_area] 조회에서 KeyError로 500이 난다.
    raw = llm_escalation.LLMParseResult(intent="skin_trouble", body_area="손목")

    parsed = llm_escalation.validate_llm_result(raw, "손목에 뭐가 났어")

    assert parsed is not None
    assert parsed.entities["body_area"] is None


def test_validate_llm_result_rejects_out_of_enum_intent() -> None:
    raw = llm_escalation.LLMParseResult(intent="not_a_real_intent")

    assert llm_escalation.validate_llm_result(raw, "메시지") is None


async def test_escalation_failure_falls_back_to_rule_based_clarification(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def failing_escalate(message: str, persona_context: str | None = None) -> None:
        return None

    monkeypatch.setattr(logic, "escalate_parse", failing_escalate)
    session_id = await _create_session(client, persona_headers)

    body = await _send(client, persona_headers, session_id, "그거 왜그럴까")

    assert body["reply_type"] == "clarification"


async def test_escalation_daily_cap_stops_further_llm_calls(
    client: AsyncClient,
    db_session: AsyncSession,
    persona_headers: dict[str, str],
    monkeypatch,
) -> None:
    call_count = 0

    async def fake_escalate(message: str, persona_context: str | None = None) -> ParsedMessage:
        nonlocal call_count
        call_count += 1
        return ParsedMessage(
            intent="skin_condition",
            entities=_EMPTY_ENTITIES,
            risk_terms=[],
            normalized_query=message,
            parse_confidence=0.75,
        )

    monkeypatch.setattr(logic, "escalate_parse", fake_escalate)
    monkeypatch.setattr(logic.settings, "chat_llm_daily_cap_per_persona", 1)

    session_id = await _create_session(client, persona_headers)
    await _send(client, persona_headers, session_id, "완전히 관련 없는 이야기예요")

    message = (
        await db_session.execute(select(SosMessage).where(SosMessage.llm_escalated.is_(True)))
    ).scalar_one()
    message.created_at = datetime(2026, 8, 20, 16, 0, tzinfo=UTC)
    await db_session.commit()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = datetime(2026, 8, 20, 16, 30, tzinfo=UTC)
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr(logic, "datetime", FrozenDateTime)
    await _send(client, persona_headers, session_id, "이것도 전혀 관련 없는 이야기입니다")

    # 상한이 1이라 두 번째 저신뢰 메시지는 escalate_parse를 아예 호출하지 않아야 한다.
    assert call_count == 1


async def test_escalation_daily_cap_of_zero_disables_escalation_entirely(
    client: AsyncClient, persona_headers: dict[str, str], monkeypatch
) -> None:
    async def fake_escalate(message: str, persona_context: str | None = None) -> ParsedMessage:
        raise AssertionError("cap=0이면 escalate_parse가 아예 호출되면 안 된다")

    monkeypatch.setattr(logic, "escalate_parse", fake_escalate)
    monkeypatch.setattr(logic.settings, "chat_llm_daily_cap_per_persona", 0)

    session_id = await _create_session(client, persona_headers)
    body = await _send(client, persona_headers, session_id, "완전히 관련 없는 이야기예요")

    assert body["reply_type"] == "clarification"


async def test_compute_chat_metrics_reflects_successful_escalation(
    client: AsyncClient,
    persona_headers: dict[str, str],
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    async def fake_escalate(message: str, persona_context: str | None = None) -> ParsedMessage:
        return ParsedMessage(
            intent="skin_condition",
            entities=_EMPTY_ENTITIES,
            risk_terms=[],
            normalized_query=message,
            parse_confidence=0.75,
        )

    monkeypatch.setattr(logic, "escalate_parse", fake_escalate)
    session_id = await _create_session(client, persona_headers)
    await _send(client, persona_headers, session_id, "완전히 관련 없는 이야기예요")

    metrics = await logic.compute_chat_metrics(db_session, persona_id=TEST_PERSONA_ID)

    assert metrics["total_messages"] == 1
    assert metrics["rule_only_rate"] == 0.0
