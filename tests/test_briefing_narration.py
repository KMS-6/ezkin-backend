"""선택적 LLM 문장화(system_architecture.md 5.8절)의 안전한 폴백 검증.

실제 Anthropic API를 호출하지 않는다 — 테스트 환경엔 AAC_ANTHROPIC_API_KEY가
설정돼 있지 않으므로(tests/conftest.py 참고), 네트워크 호출 없이 즉시 None을
반환해 호출부가 기존 템플릿 summary로 폴백하는지만 확인한다.
"""

from app.modules.briefings.narration import narrate_briefing


async def test_narrate_briefing_returns_none_without_api_key() -> None:
    result = await narrate_briefing([("sleep", "수면 4.0시간 미만")], None)

    assert result is None
