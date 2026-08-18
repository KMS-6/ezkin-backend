"""저신뢰도 파싱 escalation — 기능명세서_chatbot.md 10.2절 4단계, 10.5절.

parse_confidence < 0.60일 때만 호출된다. API 키가 설정돼 있지 않거나(기본값), SDK가
설치돼 있지 않거나, 호출 자체가 실패·타임아웃되면 예외를 던지지 않고 조용히 None을
반환한다 — 호출부는 이 경우 기존 규칙 기반 파싱 결과로 계속 진행한다(17절 가용성
원칙: LLM 장애·부재에도 대부분의 메시지는 정상 응답이 가능해야 한다).

LLM 결과도 7.1절 slot 스키마를 벗어날 수 없다(10.2절 5단계) — intent는 nlu.INTENTS
안에서만, 나머지 entity 값들도 각각의 별칭 사전(BODY_AREA_ALIASES 등)에 등록된 정규화
ID 안에서만 허용한다. 그 외 값은 무효 처리해 None/빈 리스트로 되돌린다 — 자유 텍스트가
그대로 넘어가면 규칙 엔진이 코드 상수로 가정하는 별칭 사전 키 조회(예:
BODY_AREA_ALIASES[body_area])에서 KeyError가 날 수 있다.
"""

from pydantic import BaseModel

from app.core.config import settings
from app.modules.triggers.nlu import (
    BODY_AREA_ALIASES,
    FOOD_ALIASES,
    INGREDIENT_ALIASES,
    INTENTS,
    PRODUCT_TYPE_ALIASES,
    SYMPTOM_ALIASES,
    TIME_ALIASES,
    ParsedMessage,
)

ESCALATION_TIMEOUT_SECONDS = 8.0
ESCALATION_MAX_TOKENS = 300

# 10.5절: 시스템 프롬프트는 캐시 가능한 고정 블록으로 분리하고, few-shot 예시는 2개
# 이하로 제한한다. 각 entity는 반드시 아래 나열된 정규화 ID로만 채워야 한다 — 이 목록에
# 없는 값은 서버가 무효 처리해 버리므로(위 모듈 docstring 참고), 목록을 프롬프트에 직접
# 나열해 모델이 임의 자유 텍스트 대신 정확한 ID를 고르게 한다.
_SYSTEM_PROMPT = (
    "당신은 피부 관리 챗봇의 발화 파서입니다. 답변 문장을 생성하지 말고, 사용자 메시지를 "
    "주어진 스키마에 맞는 intent와 entity로만 분류하세요.\n\n"
    f"intent는 다음 중 하나여야 합니다: {', '.join(INTENTS)}\n\n"
    "entity 값은 아래 정규화 ID만 사용하세요(자유 텍스트 금지). 확실히 언급되지 않았으면 "
    "비워두세요.\n"
    f"- ingredient_names: {', '.join(INGREDIENT_ALIASES)}\n"
    f"- body_area: {', '.join(BODY_AREA_ALIASES)}\n"
    f"- symptoms: {', '.join(SYMPTOM_ALIASES)}\n"
    f"- food_type: {', '.join(FOOD_ALIASES)}\n"
    f"- product_type: {', '.join(PRODUCT_TYPE_ALIASES)}\n"
    f"- time: {', '.join(TIME_ALIASES)}"
)

_FEW_SHOT_EXAMPLES: tuple[tuple[str, dict], ...] = (
    (
        "오늘 레티놀 써도 돼?",
        {"intent": "product_usage", "ingredient_names": ["retinol"], "time": "today"},
    ),
    ("턱에 뭐가 났어", {"intent": "skin_trouble", "body_area": "chin"}),
)


class LLMParseResult(BaseModel):
    intent: str
    ingredient_names: list[str] = []
    product_type: str | None = None
    body_area: str | None = None
    symptoms: list[str] = []
    food_type: str | None = None
    time: str | None = None


def _valid_or_none(value: str | None, aliases: dict) -> str | None:
    return value if value in aliases else None


def validate_llm_result(result: LLMParseResult, message: str) -> ParsedMessage | None:
    """10.2절 5단계: LLM 결과를 7.1절 slot 스키마로 강제한다. intent가 nlu.INTENTS
    밖이거나, entity 값이 각 별칭 사전의 정규화 ID 밖이면 그 값을 버린다(전체를
    버리지는 않는다 — intent 자체가 무효일 때만 호출부가 None으로 취급해 폴백한다).
    """
    if result.intent not in INTENTS:
        return None

    entities = {
        "product_name": None,
        "ingredient_names": [i for i in result.ingredient_names if i in INGREDIENT_ALIASES],
        "product_type": _valid_or_none(result.product_type, PRODUCT_TYPE_ALIASES),
        "body_area": _valid_or_none(result.body_area, BODY_AREA_ALIASES),
        "symptoms": [s for s in result.symptoms if s in SYMPTOM_ALIASES],
        "food_type": _valid_or_none(result.food_type, FOOD_ALIASES),
        "time": _valid_or_none(result.time, TIME_ALIASES),
    }
    return ParsedMessage(
        intent=result.intent,
        entities=entities,
        risk_terms=[],
        normalized_query=message,
        # 10.2절 4단계를 거친 결과는 확정 파싱으로 취급한다(재-escalation 없음).
        parse_confidence=0.75,
    )


async def escalate_parse(message: str) -> ParsedMessage | None:
    """LLM으로 파싱을 보정한다. 키 미설정·SDK 부재·호출 실패 시 None."""
    api_key = settings.anthropic_api_key
    if api_key is None:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    few_shot_messages: list[dict] = []
    for text, expected in _FEW_SHOT_EXAMPLES:
        few_shot_messages.append({"role": "user", "content": text})
        expected_json = LLMParseResult(**expected).model_dump_json()
        few_shot_messages.append({"role": "assistant", "content": expected_json})

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key.get_secret_value())
        response = await client.with_options(timeout=ESCALATION_TIMEOUT_SECONDS).messages.parse(
            model=settings.chat_llm_model,
            max_tokens=ESCALATION_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[*few_shot_messages, {"role": "user", "content": message}],
            output_format=LLMParseResult,
        )
    except Exception:
        return None

    result = response.parsed_output
    if result is None:
        return None
    return validate_llm_result(result, message)
