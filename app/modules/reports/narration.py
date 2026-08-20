"""선택적 LLM 문장화 — 기간 Report summary 자연어 다듬기(system_architecture.md 5.7/8절).

Rule Engine이 계산한 관찰·패턴·권고 사실만 참고해 자연스럽게 재문장화하고, 새로운
수치·제품명·인과 단정을 만들지 않는다. API 키 미설정·SDK 부재·호출 실패·안전 필터
실패 시 None을 반환해 호출부가 기존 템플릿 summary로 폴백하게 한다(P0/장애 fallback은
템플릿만으로 완결한다는 원칙).
"""

from pydantic import BaseModel

from app.core.config import settings
from app.modules.reports.safety import is_safe

NARRATION_TIMEOUT_SECONDS = 10.0
NARRATION_MAX_TOKENS = 300

_SYSTEM_PROMPT = (
    "당신은 피부 케어 기간 리포트 요약 문장을 다듬는 보조입니다. 아래 제공된 관찰·패턴·"
    "권고 사실만 자연스러운 한국어 문장으로 다시 표현하세요. 새로운 수치, 원인 단정, "
    "제품명, 의료적 진단 표현을 만들지 마세요. 제공되지 않은 사실을 추가하지 마세요."
)


class ReportNarrationResult(BaseModel):
    summary: str


def _facts_prompt(content: dict) -> str:
    lines = [f"요약 사실: {content['summary']}"]
    for key in ("observations", "patterns", "recommendations"):
        for item in content.get(key, []):
            lines.append(f"- {item['text']}")
    return "\n".join(lines)


async def narrate_report(content: dict) -> str | None:
    """LLM으로 리포트 summary를 재문장화한다. 키 미설정·SDK 부재·호출 실패·안전 필터
    실패 시 None."""
    api_key = settings.openai_api_key
    if api_key is None:
        return None

    try:
        import openai
    except ImportError:
        return None

    try:
        client = openai.AsyncOpenAI(api_key=api_key.get_secret_value())
        response = await client.with_options(
            timeout=NARRATION_TIMEOUT_SECONDS
        ).chat.completions.parse(
            model=settings.narration_llm_model,
            max_completion_tokens=NARRATION_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _facts_prompt(content)},
            ],
            response_format=ReportNarrationResult,
        )
    except Exception:
        return None

    result = response.choices[0].message.parsed
    if result is None or not result.summary.strip():
        return None
    if not is_safe(result.summary):
        return None
    return result.summary.strip()
