"""SOS 챗봇 자연어 파서 — 기능명세서_chatbot.md 7절 intent·entity 구조화.

10.2절 1~3단계(정규화 사전·정규식 slot filling → parse_confidence 계산)까지만 다룬다.
4단계(parse_confidence < 0.60일 때 저비용 LLM으로 보정)는 아직 연동돼 있지 않다 —
지금은 낮은 신뢰도를 결정적 fallback(재질문)으로 안전하게 처리한다(17절 가용성 원칙:
LLM 장애·부재에도 대부분의 메시지는 정상 응답이 가능해야 한다).

FAQ 매칭(resolve_faq)은 이 파서와 별개의 자체 점수 체계를 그대로 유지한다 — 여기서 계산한
parse_confidence는 FAQ 채택 여부를 아직 좌우하지 않는다(8.2절의 "intent로 FAQ 후보를
좁힌다"는 다음 단계 작업이다).
"""

import re
from dataclasses import dataclass, field

INTENTS = (
    "food_aftercare",
    "skin_trouble",
    "product_usage",
    "product_combination",
    "product_alternative",
    "routine_order",
    "skin_condition",
    "sunscreen",
    "service_explanation",
    "high_risk_symptom",
    "out_of_scope",
    "unknown",
)

# 7.3절: 관리자 승인 synonym을 대체하는 MVP용 최소 별칭 사전. 카테고리별 정규화 ID로
# 매핑한다 — 임의로 유사어를 합치지 않고 여기 등록된 것만 같은 개체로 취급한다.
INGREDIENT_ALIASES: dict[str, tuple[str, ...]] = {
    "retinol": ("레티놀", "레티노이드", "retinol"),
    "vitamin_c": ("비타민c", "비타민 c", "아스코르빈산", "vitamin c"),
    "niacinamide": ("나이아신아마이드",),
    "salicylic_acid": ("살리실산", "bha"),
    "hyaluronic_acid": ("히알루론산", "히알루론"),
    "centella": ("센텔라", "병풀"),
    "panthenol": ("판테놀",),
    "ceramide": ("세라마이드",),
}

BODY_AREA_ALIASES: dict[str, tuple[str, ...]] = {
    "chin": ("턱",),
    "forehead": ("이마",),
    "cheek": ("볼", "뺨"),
    "nose": ("코",),
    "around_eyes": ("눈가", "눈 밑"),
    "around_mouth": ("입가", "입술 주변"),
}

SYMPTOM_ALIASES: dict[str, tuple[str, ...]] = {
    "redness": ("붉음", "홍조", "빨개"),
    "stinging": ("따가움", "따가워", "화끈"),
    "swelling": ("부종", "부어"),
    "trouble": ("트러블", "뾰루지", "여드름"),
    "dryness": ("건조", "당김", "푸석"),
    "itching": ("가려움", "간지러워"),
}

FOOD_ALIASES: dict[str, tuple[str, ...]] = {
    "late_night_meal": ("야식",),
    "spicy": ("매운", "자극적인 음식"),
    "fried": ("튀김",),
    "alcohol": ("술", "음주"),
}

PRODUCT_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "cleanser": ("클렌저", "세안제", "폼클렌징"),
    "toner": ("토너", "스킨"),
    "serum": ("세럼", "앰플"),
    "moisturizer": ("크림", "로션", "수분크림"),
    "sunscreen": ("선크림", "자외선차단제"),
    "mask": ("마스크팩", "시트마스크"),
}

TIME_ALIASES: dict[str, tuple[str, ...]] = {
    "today": ("오늘",),
    "tonight": ("오늘 밤", "밤에"),
    "morning": ("아침",),
    "now": ("지금",),
}

# intent 판별용 신호 문구(우선순위 순서로 검사 — _detect_intent 참고).
COMBINATION_CUES = ("같이", "함께", "동시에")
USAGE_CUES = ("써도", "발라도", "사용해도", "써야", "발라야")
ALTERNATIVE_CUES = ("뭐 쓰지", "뭐가 좋을까", "추천", "대신 뭐", "대체")
ROUTINE_ORDER_CUES = ("순서", "다음에 뭐", "먼저 발라", "바르는 순서")
SUNSCREEN_CUES = ("선크림", "자외선차단")
SERVICE_EXPLANATION_CUES = ("위험도가 뭐", "무슨 뜻", "위험도란", "이게 뭐야")
TROUBLE_CUES = ("났어", "생겼어", "돋아")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _extract_many(normalized: str, aliases: dict[str, tuple[str, ...]]) -> list[str]:
    return [
        key for key, phrases in aliases.items() if any(_normalize(p) in normalized for p in phrases)
    ]


def _extract_one(normalized: str, aliases: dict[str, tuple[str, ...]]) -> str | None:
    matches = _extract_many(normalized, aliases)
    return matches[0] if matches else None


def _any_cue(normalized: str, cues: tuple[str, ...]) -> bool:
    return any(_normalize(cue) in normalized for cue in cues)


@dataclass
class ParsedMessage:
    intent: str
    entities: dict = field(default_factory=dict)
    risk_terms: list[str] = field(default_factory=list)
    normalized_query: str = ""
    parse_confidence: float = 0.0


def _detect_intent(
    normalized: str,
    ingredient_names: list[str],
    body_area: str | None,
    symptoms: list[str],
    food_type: str | None,
) -> str:
    if len(ingredient_names) >= 2:
        return "product_combination"
    if _any_cue(normalized, SUNSCREEN_CUES):
        return "sunscreen"
    if _any_cue(normalized, ALTERNATIVE_CUES):
        return "product_alternative"
    if _any_cue(normalized, ROUTINE_ORDER_CUES):
        return "routine_order"
    if ingredient_names and _any_cue(normalized, USAGE_CUES):
        return "product_usage"
    if food_type is not None:
        return "food_aftercare"
    if _any_cue(normalized, TROUBLE_CUES) or (symptoms and body_area):
        return "skin_trouble"
    if symptoms:
        return "skin_condition"
    if _any_cue(normalized, SERVICE_EXPLANATION_CUES):
        return "service_explanation"
    if ingredient_names:
        return "product_usage"
    return "unknown"


def parse_message(message: str) -> ParsedMessage:
    """규칙 기반 1차 slot filling(10.2절 1~2단계) — LLM을 호출하지 않는다."""
    normalized = _normalize(message)

    ingredient_names = _extract_many(normalized, INGREDIENT_ALIASES)
    body_area = _extract_one(normalized, BODY_AREA_ALIASES)
    symptoms = _extract_many(normalized, SYMPTOM_ALIASES)
    food_type = _extract_one(normalized, FOOD_ALIASES)
    product_type = _extract_one(normalized, PRODUCT_TYPE_ALIASES)
    time = _extract_one(normalized, TIME_ALIASES)

    intent = _detect_intent(normalized, ingredient_names, body_area, symptoms, food_type)

    entities = {
        # PRODUCT_CATALOG 기반 제품명 매칭은 MVP 범위 밖이라 항상 None이다.
        "product_name": None,
        "ingredient_names": ingredient_names,
        "product_type": product_type,
        "body_area": body_area,
        "symptoms": symptoms,
        "food_type": food_type,
        "time": time,
    }

    # 10.2절 2단계: 채워진 slot 개수 + intent 확정 여부로 parse_confidence를 근사한다.
    filled_slots = sum(
        1
        for key, value in entities.items()
        if key != "product_name" and (value if isinstance(value, list) else value is not None)
    )
    confidence = 0.5 if intent != "unknown" else 0.0
    confidence += min(filled_slots * 0.15, 0.45)
    confidence = round(min(confidence, 1.0), 2)

    return ParsedMessage(
        intent=intent,
        entities=entities,
        risk_terms=[],
        normalized_query=normalized,
        parse_confidence=confidence,
    )
