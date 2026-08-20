"""선택적 LLM 문장화(system_architecture.md 5.7절)의 안전한 폴백 검증.

실제 Anthropic API를 호출하지 않는다 — 테스트 환경엔 AAC_ANTHROPIC_API_KEY가
설정돼 있지 않으므로(tests/conftest.py 참고), 네트워크 호출 없이 즉시 None을
반환해 호출부가 기존 템플릿 summary로 폴백하는지만 확인한다.
"""

from app.modules.reports.narration import narrate_report


async def test_narrate_report_returns_none_without_api_key() -> None:
    content = {
        "summary": "최근 14일간 3회의 관찰 데이터를 분석했어요.",
        "observations": [{"text": "평균 지표: dryness 0.3", "evidence_ids": ["scan-1"]}],
        "patterns": [],
        "recommendations": [],
    }

    result = await narrate_report(content)

    assert result is None
