"""선택적 LLM 문장화 — Morning Briefing summary 자연어 다듬기(system_architecture.md 5.8/8절).

Rule Engine이 계산한 factors·common_knowledge 문장만 참고해 자연스럽게 재문장화하고,
새로운 사실이나 제품명을 만들지 않는다. API 키 미설정·SDK 부재·호출 실패·안전 필터
실패 시 None을 반환해 호출부가 기존 템플릿 summary로 폴백하게 한다.
"""

from pydantic import BaseModel

from app.core.config import settings
from app.modules.reports.safety import is_safe

NARRATION_TIMEOUT_SECONDS = 10.0
NARRATION_MAX_TOKENS = 200

_SYSTEM_PROMPT = (
    "당신은 피부 관리 Morning Briefing 요약 문장을 다듬는 보조입니다. 아래 제공된 관찰 "
    "사실만 자연스러운 한국어 한두 문장으로 다시 표현하세요. 새로운 수치, 원인 단정, "
    "제품명, 의료적 진단 표현을 만들지 마세요. 제공되지 않은 사실을 추가하지 마세요."
)


class BriefingNarrationResult(BaseModel):
    summary: str


def _facts_prompt(factors: list[tuple[str, str]], common_knowledge: dict | None) -> str:
    lines = [f"- {text}" for _, text in factors] or ["- 특별한 위험 요인이 관찰되지 않았어요."]
    if common_knowledge is not None:
        lines.append(f"- {common_knowledge['sentence']}")
    return "\n".join(lines)


async def narrate_briefing(
    factors: list[tuple[str, str]], common_knowledge: dict | None
) -> str | None:
    """LLM으로 Briefing summary를 재문장화한다. 키 미설정·SDK 부재·호출 실패·안전 필터
    실패 시 None."""
    api_key = settings.anthropic_api_key
    if api_key is None:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key.get_secret_value())
        response = await client.with_options(timeout=NARRATION_TIMEOUT_SECONDS).messages.parse(
            model=settings.narration_llm_model,
            max_tokens=NARRATION_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _facts_prompt(factors, common_knowledge)}],
            output_format=BriefingNarrationResult,
        )
    except Exception:
        return None

    result = response.parsed_output
    if result is None or not result.summary.strip():
        return None
    if not is_safe(result.summary):
        return None
    return result.summary.strip()
