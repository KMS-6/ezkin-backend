import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cosmetic_catalog import PersonaCosmetic
from app.models.metrics import DailyMetric
from app.models.scan import SkinScan
from app.models.sos import SosMessage
from app.modules.risk.logic import load_today_risk_context
from app.modules.triggers.faq_data import FAQ_ENTRIES
from app.modules.triggers.llm_escalation import escalate_parse
from app.modules.triggers.nlu import BODY_AREA_ALIASES, INGREDIENT_ALIASES, parse_message

PATTERN_WINDOW_HOURS = 72
PATTERN_HISTORY_DAYS = 90
IRRITATING_DIET_FLAGS = {"spicy", "late_night_meal"}
ELEVATED_THRESHOLD = 0.66
MIN_SAMPLE_SIZE = 3

KST = ZoneInfo("Asia/Seoul")

# 14절 안전 정책: 자해·극단적 선택 표현은 나머지 고위험 표현과 분리해 승인된 위기
# 상담 안내로 즉시 전환한다(safety_flag=self_harm).
SELF_HARM_KEYWORDS = ("자살", "죽고싶", "죽어버리고싶", "자해", "극단적선택")

# 14절: 호흡곤란, 급격한 부종, 번지는 발진·물집, 극심한 통증·고열, 화학물질 눈접촉·화상.
URGENT_KEYWORDS = (
    "호흡곤란",
    "숨을못",
    "숨쉬기힘",
    "의식",
    "심한부종",
    "눈이부어",
    "붓기가심",
    "번지는발진",
    "물집이",
    "극심한통증",
    "고열",
    "화학화상",
    "눈에화학물질",
    "화학물질이눈",
)

# 2절 MVP 제외 범위: 영양제·의약품 복용 추천은 하지 않고 out_of_scope로 리다이렉트한다.
SUPPLEMENT_KEYWORDS = ("영양제", "유산균", "보충제", "건강기능식품", "프로바이오틱스")

# SUPP-010류: "비타민 먹으면 ~"처럼 위 키워드에 없는 구어체도 경구 섭취 맥락(먹다·섭취·복용)과
# 결합되면 out_of_scope로 본다. 스킨케어 도포 맥락(발라·바르·도포)이 함께 있으면 성분 사용법
# 질문으로 보고 제외한다(예: "비타민C 세럼 발라도 돼요?").
GENERIC_NUTRIENT_WORDS = ("비타민", "칼슘", "오메가3", "콜라겐", "마그네슘", "아연")
ORAL_INTAKE_VERBS = ("먹으면", "먹어야", "먹을까", "먹어도", "복용", "섭취")
TOPICAL_VERBS = ("발라", "바르", "도포")

# 14절 금지 표현: 처방약 시작·중단·용량 안내는 답변을 거부하고 전문가 상담으로 전환한다
# (CHAT-SAFE-004). "약" 단독은 오탐 가능성이 있어 중단·용량 관련 동사와 결합될 때만 판정한다.
MEDICATION_ACTION_STEMS = ("끊", "중단", "용량")

# 성분 별칭은 app.modules.triggers.nlu.INGREDIENT_ALIASES로 일원화했다(7.3절). 진정·보습
# 대체품 탐색용 별칭만 여기 남긴다 — 사용자가 메시지에서 언급하는 개체가 아니라 My Shelf
# 제품의 속성이라 파서의 관심사가 아니다.
SOOTHING_ALIASES = ("판테놀", "병풀", "센텔라", "세라마이드", "알로에", "히알루론")

# 11.5절 INGREDIENT_INTERACTIONS의 축소판 — 승인된 쌍만 등록한다. 여기 없는 조합은
# "함께 사용해도 안전하다"고 단정하지 않는다(CB-08, 검증된 규칙이 없으면 안전 단정 금지).
INGREDIENT_INTERACTIONS: list[dict] = [
    {
        "pair": frozenset({"retinol", "vitamin_c"}),
        "rule_id": "rule_retinol_vitaminc_avoid",
        "faq_id": "faq_retinol_vitaminc_combo",
        "owned_guidance": "같은 루틴에서 함께 사용하면 자극 가능성이 있어요. 아침·저녁으로 나누어 "
        "사용해 보세요.",
        "general_guidance": "자극 가능성이 있는 조합으로 분류돼요",
    },
    {
        "pair": frozenset({"retinol", "salicylic_acid"}),
        "rule_id": "rule_retinol_salicylic_avoid",
        "faq_id": "faq_retinol_salicylic_combo",
        "owned_guidance": "두 성분 모두 각질 턴오버를 촉진해 함께 사용하면 자극 가능성이 있어요. "
        "아침·저녁으로 나누어 사용해 보세요.",
        "general_guidance": "자극 가능성이 있는 조합으로 분류돼요",
    },
]


def _find_interaction(ingredient_ids: list[str]) -> dict | None:
    mentioned = set(ingredient_ids)
    for entry in INGREDIENT_INTERACTIONS:
        if entry["pair"] <= mentioned:
            return entry
    return None


def _owns_product_type(
    cosmetics: list[PersonaCosmetic], product_type: str
) -> PersonaCosmetic | None:
    for cosmetic in cosmetics:
        if cosmetic.product_type == product_type:
            return cosmetic
    return None


# 8.2절 초기 기준: >=0.80 즉시 채택, 0.60~0.79는 1·2위 차이가 충분할 때만 채택, 미만이면
# 재질문·fallback. 실제 계산식·threshold는 21절에서 "Mock Data 평가셋으로 조정" 대상으로
# 명시된 미확정 값이며, 아래 _faq_score는 그 정신(키워드 겹치는 정도로 점수화)을 따르는
# 단순 휴리스틱이다(임베딩·LLM 없음, 10절 정책).
FAQ_HIGH_CONFIDENCE = 0.80
FAQ_LOW_CONFIDENCE = 0.60
FAQ_MARGIN = 0.15

CLARIFICATION_REPLY = (
    "어떤 내용이 궁금하신가요? 제품 사용 가능 여부, 사용 순서, 갑작스러운 트러블 대응 중 "
    "하나로 다시 말씀해 주시면 안내해 드릴게요."
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _mentions_any(message: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize(message)
    return any(_normalize(alias) in normalized for alias in aliases)


def is_self_harm(message: str) -> bool:
    return _mentions_any(message, SELF_HARM_KEYWORDS)


def is_urgent(message: str) -> bool:
    return _mentions_any(message, URGENT_KEYWORDS)


def is_supplement_question(message: str) -> bool:
    if _mentions_any(message, SUPPLEMENT_KEYWORDS):
        return True
    normalized = _normalize(message)
    has_nutrient_word = any(_normalize(w) in normalized for w in GENERIC_NUTRIENT_WORDS)
    has_oral_verb = any(_normalize(v) in normalized for v in ORAL_INTAKE_VERBS)
    has_topical_verb = any(_normalize(v) in normalized for v in TOPICAL_VERBS)
    return has_nutrient_word and has_oral_verb and not has_topical_verb


def is_medication_question(message: str) -> bool:
    normalized = _normalize(message)
    return "약" in normalized and any(stem in normalized for stem in MEDICATION_ACTION_STEMS)


def _faq_score(normalized_query: str, entry: dict) -> float:
    """키워드가 겹치는 정도로 점수를 매긴다: 매칭된 키워드 중 가장 긴 것일수록(더
    구체적인 문구일수록), 매칭된 키워드가 여러 개일수록(여러 신호가 겹칠수록) 점수가
    높아진다."""
    matched = [nk for k in entry["keywords"] if (nk := _normalize(k)) and nk in normalized_query]
    if not matched:
        return 0.0
    longest = max(len(k) for k in matched)
    score = 0.75
    if longest >= 3:
        score += 0.1
    score += min((len(matched) - 1) * 0.05, 0.15)
    return round(min(score, 1.0), 2)


def search_faq(message: str, candidates: list[dict] | None = None) -> list[tuple[float, dict]]:
    """후보 FAQ를 점수 순으로 정렬해 반환한다(점수 0 초과만). `candidates`를 생략하면
    전체 FAQ_ENTRIES에서 찾는다."""
    normalized = _normalize(message)
    pool = candidates if candidates is not None else FAQ_ENTRIES
    scored = [(score, entry) for entry in pool if (score := _faq_score(normalized, entry)) > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def resolve_faq(message: str, intent: str | None = None) -> dict:
    """8.2절 검색 순서 2·4~6단계: intent로 후보를 먼저 좁힌 뒤 점수를 합산해 1위를
    고르되, 기준 미달이거나 1·2위가 모호하면 임의로 답변하지 않는다(CB-03, CB-04).

    intent로 좁힌 후보에서 아무것도 못 찾으면(점수 0 초과 후보가 없으면) intent 분류가
    틀렸을 가능성을 감안해 전체 FAQ에서 다시 찾는다 — intent 좁히기가 오히려 커버리지를
    줄이는 회귀를 막기 위함이다.

    반환값: {"selected": FAQ|None, "score": float, "candidates": [FAQ, ...]}.
    `candidates`는 1·2위가 모호해 재질문이 필요할 때만 채워진다.
    """
    narrowed = None
    if intent and intent != "unknown":
        narrowed = [entry for entry in FAQ_ENTRIES if entry.get("intent") == intent]

    ranked = search_faq(message, narrowed) if narrowed else []
    if not ranked:
        ranked = search_faq(message)
    if not ranked:
        return {"selected": None, "score": 0.0, "candidates": []}

    top_score, top_entry = ranked[0]
    if top_score >= FAQ_HIGH_CONFIDENCE:
        return {"selected": top_entry, "score": top_score, "candidates": []}

    if top_score >= FAQ_LOW_CONFIDENCE:
        second_score, second_entry = ranked[1] if len(ranked) > 1 else (0.0, None)
        if second_entry is None or (top_score - second_score) >= FAQ_MARGIN:
            return {"selected": top_entry, "score": top_score, "candidates": []}
        return {"selected": None, "score": top_score, "candidates": [top_entry, second_entry]}

    return {"selected": None, "score": top_score, "candidates": []}


def _owns_ingredient(
    cosmetics: list[PersonaCosmetic], aliases: tuple[str, ...]
) -> PersonaCosmetic | None:
    for cosmetic in cosmetics:
        raw_items = [_normalize(item) for item in (cosmetic.ingredients_raw or [])]
        if any(_normalize(alias) in item for alias in aliases for item in raw_items):
            return cosmetic
    return None


def _product_label(cosmetic: PersonaCosmetic) -> str:
    return f"{cosmetic.brand} {cosmetic.product_name}"


def _answer(
    reply: str,
    *,
    faq_id: str,
    version: int,
    match_score: float,
    referenced: list[str],
    used_contexts: list[str],
    intent: str,
    parse_confidence: float,
    llm_escalated: bool,
    decision: dict | None = None,
) -> dict:
    return {
        "reply_type": "answer",
        "reply": reply,
        "matched_faq": {"faq_id": faq_id, "version": version, "match_score": match_score},
        "decision": decision,
        "referenced_cosmetic_ids": referenced,
        "used_contexts": used_contexts,
        "safety_flag": None,
        "expert_referral_suggested": False,
        "intent": intent,
        "parse_confidence": parse_confidence,
        "llm_escalated": llm_escalated,
    }


async def build_pattern_analysis(db: AsyncSession, scan: SkinScan) -> dict:
    window_start = scan.captured_at - timedelta(hours=PATTERN_WINDOW_HOURS)
    window_end = scan.captured_at

    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == scan.persona_id,
            DailyMetric.metric_date >= window_start.date(),
            DailyMetric.metric_date <= window_end.date(),
        )
    )
    metrics_in_window = list(metrics_result.scalars())

    raw_facts = []
    short_sleep_days = [
        m for m in metrics_in_window if m.sleep_hours is not None and m.sleep_hours < 6
    ]
    if short_sleep_days:
        raw_facts.append(
            {
                "type": "sleep",
                "text": f"최근 72시간 내 수면 6시간 미만 날이 {len(short_sleep_days)}일 있었어요.",
            }
        )
    irritating_days = [m for m in metrics_in_window if m.diet_flag in IRRITATING_DIET_FLAGS]
    if irritating_days:
        raw_facts.append(
            {
                "type": "diet",
                "text": f"자극 유발 가능 식습관이 {len(irritating_days)}일 기록됐어요.",
            }
        )

    history_start = (window_end - timedelta(days=PATTERN_HISTORY_DAYS)).date()
    all_metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == scan.persona_id,
            DailyMetric.metric_date >= history_start,
        )
    )
    condition_days = [
        m
        for m in all_metrics_result.scalars()
        if (m.sleep_hours is not None and m.sleep_hours < 6) or m.diet_flag in IRRITATING_DIET_FLAGS
    ]

    all_scans_result = await db.execute(
        select(SkinScan).where(
            SkinScan.persona_id == scan.persona_id,
            SkinScan.status == "completed",
            SkinScan.captured_at >= window_end - timedelta(days=PATTERN_HISTORY_DAYS),
        )
    )
    all_scans = list(all_scans_result.scalars())

    match_count = 0
    for day in condition_days:
        next_day_scans = [
            s for s in all_scans if s.captured_at.date() == day.metric_date + timedelta(days=1)
        ]
        if any(
            s.scores and any(v >= ELEVATED_THRESHOLD for v in s.scores.values())
            for s in next_day_scans
        ):
            match_count += 1

    sample_size = len(condition_days)
    observed_pattern = None
    if sample_size >= MIN_SAMPLE_SIZE:
        observed_pattern = {
            "text": f"비슷한 조건 {sample_size}번 중 {match_count}번 함께 높은 수치가 관찰됐어요.",
            "sample_size": sample_size,
            "match_count": match_count,
        }

    return {
        "window": {"start": window_start, "end": window_end},
        "raw_facts": raw_facts,
        "observed_pattern": observed_pattern,
        "common_knowledge": None,
        "disclaimer": "통계적 상관관계는 의료 진단이 아닌 예방적 참고용 관찰입니다.",
    }


async def _load_today_risk(db: AsyncSession, persona_id: str) -> tuple[str, list[str]]:
    now = datetime.now(KST)
    context = await load_today_risk_context(db, persona_id, now.date(), now)
    return context["risk_level"], [text for _, text in context["factors"]]


async def _load_owned_cosmetics(db: AsyncSession, persona_id: str) -> list[PersonaCosmetic]:
    result = await db.execute(
        select(PersonaCosmetic).where(
            PersonaCosmetic.persona_id == persona_id, PersonaCosmetic.deleted_at.is_(None)
        )
    )
    return list(result.scalars())


async def _escalations_today(db: AsyncSession, persona_id: str) -> int:
    """비용 방어: 페르소나당 하루 LLM escalation 호출 횟수를 센다(KST 기준 자정
    경계). settings.chat_llm_daily_cap_per_persona를 넘기면 더 escalate하지 않는다
    — 애매한 메시지가 몰려도 호출이 무한정 늘어나지 않게 막는다.
    """
    today_start_kst = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count())
        .select_from(SosMessage)
        .where(
            SosMessage.persona_id == persona_id,
            SosMessage.llm_escalated.is_(True),
            SosMessage.created_at >= today_start_kst,
        )
    )
    return result.scalar_one()


async def build_chat_reply(db: AsyncSession, persona_id: str, message: str) -> dict:
    """Rule-based SOS 챗봇 응답 — 기능명세서_chatbot.md 9·13절, API명세서.md 15.2절 확정 응답.

    답변은 서버 템플릿 치환만으로 조립하며 LLM을 쓰지 않는다(10절 LLM 사용 최소화
    정책). 파싱만 예외적으로 parse_confidence가 낮을 때 저비용 LLM으로 보정한다
    (10.2절 4단계, escalate_parse) — 그 외에는 키워드·별칭 사전 기반 규칙만 쓴다.
    """
    # 14절: 위험 키워드는 FAQ 검색보다 먼저 검사한다. 자해 표현은 일반 고위험보다 더
    # 우선해 스킨케어 안내를 전혀 섞지 않는다.
    if is_self_harm(message):
        return {
            "reply_type": "safety",
            "reply": "혼자 견디지 않으셔도 돼요. 지금 많이 힘드시다면 1393(자살예방상담전화) 등 "
            "전문 상담기관에 즉시 연락해 도움을 받아 주세요.",
            "matched_faq": None,
            "decision": None,
            "referenced_cosmetic_ids": [],
            "used_contexts": [],
            "safety_flag": "self_harm",
            "expert_referral_suggested": True,
            "intent": "high_risk_symptom",
            "parse_confidence": 1.0,
            "llm_escalated": False,
        }

    if is_urgent(message):
        return {
            "reply_type": "safety",
            "reply": "앱의 일반 관리 안내 범위를 벗어납니다. 즉시 의료기관에 문의해 주세요.",
            "matched_faq": None,
            "decision": None,
            "referenced_cosmetic_ids": [],
            "used_contexts": [],
            "safety_flag": "urgent_symptom",
            "expert_referral_suggested": True,
            "intent": "high_risk_symptom",
            "parse_confidence": 1.0,
            "llm_escalated": False,
        }

    if is_supplement_question(message):
        return {
            "reply_type": "out_of_scope",
            "reply": "영양제·건강기능식품의 섭취 여부나 용량은 안내하지 않아요. 제품 라벨이나 "
            "전문가 확인을 권장하며, 저는 피부·화장품 관리 범위에서 도와드릴 수 있어요.",
            "matched_faq": None,
            "decision": None,
            "referenced_cosmetic_ids": [],
            "used_contexts": [],
            "safety_flag": None,
            "expert_referral_suggested": False,
            "intent": "out_of_scope",
            "parse_confidence": 1.0,
            "llm_escalated": False,
        }

    if is_medication_question(message):
        return {
            "reply_type": "out_of_scope",
            "reply": "처방약의 시작·중단이나 용량은 안내하지 않아요. 처방받은 의료진과 상담해 "
            "주세요.",
            "matched_faq": None,
            "decision": None,
            "referenced_cosmetic_ids": [],
            "used_contexts": [],
            "safety_flag": None,
            "expert_referral_suggested": True,
            "intent": "out_of_scope",
            "parse_confidence": 1.0,
            "llm_escalated": False,
        }

    owned = await _load_owned_cosmetics(db, persona_id)
    parsed = parse_message(message)
    # 10.2절 4단계: parse_confidence가 낮을 때만 저비용 LLM으로 보정한다. 키 미설정·
    # 호출 실패·일일 상한 초과 시 규칙 기반 결과를 그대로 쓴다.
    llm_escalated = False
    if parsed.parse_confidence < FAQ_LOW_CONFIDENCE:
        cap = settings.chat_llm_daily_cap_per_persona
        if cap > 0 and await _escalations_today(db, persona_id) < cap:
            escalated = await escalate_parse(message)
            if escalated is not None:
                parsed = escalated
                llm_escalated = True
    mentioned_ingredients = parsed.entities["ingredient_names"]

    # 9절 규칙 예시 + 11.5절 INGREDIENT_INTERACTIONS: 2개 이상 성분이 언급되면 승인된
    # 상호작용 규칙이 있는 조합만 avoid_same_routine으로 안내하고, 없으면 안전하다고
    # 단정하지 않는다(CB-08).
    if len(mentioned_ingredients) >= 2:
        interaction = _find_interaction(mentioned_ingredients)
        if interaction is not None:
            id_a, id_b = sorted(interaction["pair"])
            product_a = _owns_ingredient(owned, INGREDIENT_ALIASES[id_a])
            product_b = _owns_ingredient(owned, INGREDIENT_ALIASES[id_b])
            if product_a and product_b:
                reply = (
                    f"{_product_label(product_a)}와(과) {_product_label(product_b)}는 "
                    f"{interaction['owned_guidance']}"
                )
                referenced = [str(product_a.id), str(product_b.id)]
            else:
                name_a, name_b = INGREDIENT_ALIASES[id_a][0], INGREDIENT_ALIASES[id_b][0]
                reply = (
                    f"{name_a}과 {name_b} 조합은 {interaction['general_guidance']}. 등록된 "
                    "화장품에서 두 성분을 모두 확인하지 못해 My Shelf에 등록하면 더 정확히 "
                    "안내할 수 있어요."
                )
                referenced = [str(c.id) for c in (product_a, product_b) if c]
            return _answer(
                reply,
                faq_id=interaction["faq_id"],
                version=1,
                match_score=0.9,
                referenced=referenced,
                used_contexts=["owned_products"],
                decision={"rule_id": interaction["rule_id"], "code": "AVOID_SAME_ROUTINE"},
                intent=parsed.intent,
                parse_confidence=parsed.parse_confidence,
                llm_escalated=llm_escalated,
            )
        return _answer(
            "언급하신 성분 조합은 검증된 상호작용 규칙이 없어 사용 가능 여부를 단정하기 "
            "어려워요. 각각 다른 시간대에 나누어 사용하는 것을 권장해요.",
            faq_id="faq_unverified_combination",
            version=1,
            match_score=0.7,
            referenced=[],
            used_contexts=[],
            intent=parsed.intent,
            parse_confidence=parsed.parse_confidence,
            llm_escalated=llm_escalated,
        )

    # 9절 규칙 예시: 레티놀 보유 + 고위험이면 오늘 사용을 생략하고 진정/보습 대체 제품을 찾는다.
    if "retinol" in mentioned_ingredients:
        retinol_product = _owns_ingredient(owned, INGREDIENT_ALIASES["retinol"])
        if retinol_product is None:
            return _answer(
                "등록된 화장품에서 레티놀 제품을 확인하지 못했어요. My Shelf에 제품을 등록하면 "
                "성분과 오늘 피부 상태를 함께 확인해 안내할 수 있어요.",
                faq_id="faq_retinol_today",
                version=1,
                match_score=0.85,
                referenced=[],
                used_contexts=["owned_products"],
                intent=parsed.intent,
                parse_confidence=parsed.parse_confidence,
                llm_escalated=llm_escalated,
            )

        risk_level, factors = await _load_today_risk(db, persona_id)
        used_contexts = ["owned_products", "today_risk_assessment"]
        if risk_level in ("high", "very_high"):
            condition_summary = (
                f"오늘은 {', '.join(factors)}이(가) 함께 관찰돼"
                if factors
                else "오늘은 자극 가능성이 있어"
            )
            alternative = _owns_ingredient(owned, SOOTHING_ALIASES)
            if alternative is not None:
                reply = (
                    f"{condition_summary} {_product_label(retinol_product)}은(는) 쉬어 보세요. "
                    f"대신 {_product_label(alternative)}로 보습·진정 위주로 관리해 주세요."
                )
                referenced = [str(retinol_product.id), str(alternative.id)]
            else:
                reply = (
                    f"{condition_summary} {_product_label(retinol_product)}은(는) 쉬어 보세요. "
                    "등록된 진정·보습 제품이 없어 일반적인 보습 관리만 안내해요."
                )
                referenced = [str(retinol_product.id)]
            return _answer(
                reply,
                faq_id="faq_retinol_today",
                version=1,
                match_score=0.92,
                referenced=referenced,
                used_contexts=used_contexts,
                decision={"rule_id": "rule_retinol_high_risk", "code": "SKIP_PRODUCT"},
                intent=parsed.intent,
                parse_confidence=parsed.parse_confidence,
                llm_escalated=llm_escalated,
            )

        return _answer(
            f"오늘은 특별한 자극 요인이 없어 {_product_label(retinol_product)}을(를) 평소대로 "
            "사용해도 괜찮아요.",
            faq_id="faq_retinol_today",
            version=1,
            match_score=0.92,
            referenced=[str(retinol_product.id)],
            used_contexts=used_contexts,
            decision={"rule_id": "rule_retinol_normal_risk", "code": "USE_PRODUCT"},
            intent=parsed.intent,
            parse_confidence=parsed.parse_confidence,
            llm_escalated=llm_escalated,
        )

    # 2절 원칙: 새 제품 구매를 우선 권하지 않고 보유 화장품을 먼저 활용한다.
    if parsed.intent == "product_alternative":
        alternative = _owns_ingredient(owned, SOOTHING_ALIASES)
        if alternative is not None:
            reply = (
                f"등록된 제품 중에서는 {_product_label(alternative)}가 진정·보습 목적으로 "
                "참고할 만해요."
            )
            referenced = [str(alternative.id)]
            decision = {"rule_id": "rule_alternative_from_shelf", "code": "USE_PRODUCT"}
        else:
            reply = (
                "등록된 화장품에서 진정·보습 목적의 제품을 확인하지 못했어요. My Shelf에 보유 "
                "제품을 등록하면 있는 제품 중에서 먼저 안내할 수 있어요."
            )
            referenced = []
            decision = None
        return _answer(
            reply,
            faq_id="faq_product_alternative",
            version=1,
            match_score=0.85,
            referenced=referenced,
            used_contexts=["owned_products"],
            decision=decision,
            intent=parsed.intent,
            parse_confidence=parsed.parse_confidence,
            llm_escalated=llm_escalated,
        )

    if parsed.intent == "sunscreen":
        sunscreen_product = _owns_product_type(owned, "sunscreen")
        if sunscreen_product is not None:
            reply = f"{_product_label(sunscreen_product)}를 2~3시간 간격으로 덧발라 주세요."
            referenced = [str(sunscreen_product.id)]
            used_contexts = ["owned_products"]
        else:
            reply = (
                "자외선 차단제는 2~3시간 간격으로 덧바르는 것이 일반적으로 권장돼요. 등록된 "
                "선크림이 없어 제품명은 안내하지 못해요."
            )
            referenced = []
            used_contexts = []
        return _answer(
            reply,
            faq_id="faq_sunscreen_reapply",
            version=1,
            match_score=0.85,
            referenced=referenced,
            used_contexts=used_contexts,
            intent=parsed.intent,
            parse_confidence=parsed.parse_confidence,
            llm_escalated=llm_escalated,
        )

    if parsed.intent == "skin_trouble":
        body_area = parsed.entities["body_area"]
        area_prefix = f"{BODY_AREA_ALIASES[body_area][0]} " if body_area is not None else ""
        alternative = _owns_ingredient(owned, SOOTHING_ALIASES)
        used_contexts = ["today_risk_assessment"]
        if alternative is not None:
            base_reply = (
                f"{area_prefix}부위는 손으로 만지거나 짜지 않고, 등록하신 "
                f"{_product_label(alternative)}로 자극 없이 진정해 주세요."
            )
            referenced = [str(alternative.id)]
            used_contexts.append("owned_products")
        else:
            base_reply = (
                f"{area_prefix}부위는 손으로 만지거나 짜지 않고, 자극이 적은 제품으로 진정 "
                "위주로 관리해 주세요."
            )
            referenced = []

        risk_level, factors = await _load_today_risk(db, persona_id)
        if risk_level in ("high", "very_high") and factors:
            reply = (
                f"오늘은 {', '.join(factors)}이(가) 함께 관찰돼 평소보다 자극에 더 주의가 "
                f"필요해요. {base_reply}"
            )
        else:
            reply = base_reply
        return _answer(
            reply,
            faq_id="faq_skin_trouble",
            version=1,
            match_score=0.85,
            referenced=referenced,
            used_contexts=used_contexts,
            intent=parsed.intent,
            parse_confidence=parsed.parse_confidence,
            llm_escalated=llm_escalated,
        )

    resolved = resolve_faq(message, parsed.intent)
    faq = resolved["selected"]
    if faq is not None:
        alternative = _owns_ingredient(owned, SOOTHING_ALIASES)
        reply = faq["reply"]
        referenced: list[str] = []
        used_contexts: list[str] = []
        if alternative is not None:
            reply = f"{reply} 등록된 {_product_label(alternative)}를 활용해 보세요."
            referenced = [str(alternative.id)]
            used_contexts = ["owned_products"]
        return _answer(
            reply,
            faq_id=faq["faq_id"],
            version=faq["version"],
            match_score=resolved["score"],
            referenced=referenced,
            used_contexts=used_contexts,
            intent=parsed.intent,
            parse_confidence=parsed.parse_confidence,
            llm_escalated=llm_escalated,
        )

    # 8.2절: 1·2위 후보가 근소해 모호하면 두 후보를 놓고 선택형 재질문을 한다(CB-04).
    if resolved["candidates"]:
        labels = " / ".join(candidate["label"] for candidate in resolved["candidates"])
        return {
            "reply_type": "clarification",
            "reply": f"{labels} 중 어떤 내용이 궁금하신가요? 조금 더 구체적으로 말씀해 "
            "주시면 정확히 안내해 드릴게요.",
            "matched_faq": None,
            "decision": None,
            "referenced_cosmetic_ids": [],
            "used_contexts": [],
            "safety_flag": None,
            "expert_referral_suggested": False,
            "intent": parsed.intent,
            "parse_confidence": parsed.parse_confidence,
            "llm_escalated": llm_escalated,
        }

    # 8.2절: 일치도 기준 미달이면 임의로 답변하지 않고 재질문한다(CB-03, CB-04).
    return {
        "reply_type": "clarification",
        "reply": CLARIFICATION_REPLY,
        "matched_faq": None,
        "decision": None,
        "referenced_cosmetic_ids": [],
        "used_contexts": [],
        "safety_flag": None,
        "expert_referral_suggested": False,
        "intent": parsed.intent,
        "parse_confidence": parsed.parse_confidence,
        "llm_escalated": llm_escalated,
    }


async def compute_chat_metrics(db: AsyncSession, persona_id: str | None = None) -> dict:
    """18.3절 운영 지표. `rule_only_rate`는 실제로 LLM escalation을 거치지 않은 메시지의
    비율이다(escalate_parse가 성공적으로 결과를 대체한 메시지만 llm_escalated=True로
    저장된다). `low_confidence_rate`는 최종 저장된 parse_confidence 기준이라 escalation이
    성공한 메시지는 보정값(0.75)으로 집계된다 — 즉 "여전히 낮은 신뢰도로 남은" 메시지
    비율이지, "escalate 됐어야 할" 메시지 비율이 아니다.
    """
    stmt = select(SosMessage)
    if persona_id is not None:
        stmt = stmt.where(SosMessage.persona_id == persona_id)
    result = await db.execute(stmt)
    messages = list(result.scalars())

    total = len(messages)
    if total == 0:
        return {
            "total_messages": 0,
            "rule_only_rate": 1.0,
            "fallback_rate": 0.0,
            "avg_parse_confidence": None,
            "low_confidence_rate": 0.0,
        }

    fallback_count = sum(1 for m in messages if m.reply_type == "clarification")
    escalated_count = sum(1 for m in messages if m.llm_escalated)
    confidences = [m.parse_confidence for m in messages if m.parse_confidence is not None]
    low_confidence_count = sum(1 for c in confidences if c < FAQ_LOW_CONFIDENCE)

    return {
        "total_messages": total,
        "rule_only_rate": round(1 - (escalated_count / total), 2),
        "fallback_rate": round(fallback_count / total, 2),
        "avg_parse_confidence": (
            round(sum(confidences) / len(confidences), 2) if confidences else None
        ),
        "low_confidence_rate": (
            round(low_confidence_count / len(confidences), 2) if confidences else 0.0
        ),
    }
