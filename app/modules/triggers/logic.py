import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cosmetic_catalog import PersonaCosmetic
from app.models.metrics import DailyMetric
from app.models.skin_scan import SkinScan
from app.modules.risk.logic import compute_risk
from app.modules.triggers.faq_data import FAQ_ENTRIES

PATTERN_WINDOW_HOURS = 72
IRRITATING_DIET_FLAGS = {"spicy", "late_night_meal", "alcohol"}
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

# 관리자 승인 synonym을 대체하는 MVP용 최소 별칭 사전(7.3절).
RETINOL_ALIASES = ("레티놀", "레티노이드", "retinol")
VITAMIN_C_ALIASES = ("비타민c", "비타민 c", "아스코르빈산", "vitamin c")
SOOTHING_ALIASES = ("판테놀", "병풀", "센텔라", "세라마이드", "알로에", "히알루론")

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


def search_faq(message: str) -> list[tuple[float, dict]]:
    """모든 FAQ 후보를 점수 순으로 정렬해 반환한다(점수 0 초과만)."""
    normalized = _normalize(message)
    scored = [
        (score, entry) for entry in FAQ_ENTRIES if (score := _faq_score(normalized, entry)) > 0
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def resolve_faq(message: str) -> dict:
    """8.2절 검색 순서 4~6단계: 점수를 합산해 1위 후보를 고르되, 기준 미달이거나
    1·2위가 모호하면 임의로 답변하지 않는다(CB-03, CB-04).

    반환값: {"selected": FAQ|None, "score": float, "candidates": [FAQ, ...]}.
    `candidates`는 1·2위가 모호해 재질문이 필요할 때만 채워진다.
    """
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

    all_metrics_result = await db.execute(
        select(DailyMetric).where(DailyMetric.persona_id == scan.persona_id)
    )
    condition_days = [
        m
        for m in all_metrics_result.scalars()
        if (m.sleep_hours is not None and m.sleep_hours < 6) or m.diet_flag in IRRITATING_DIET_FLAGS
    ]

    all_scans_result = await db.execute(
        select(SkinScan).where(
            SkinScan.persona_id == scan.persona_id, SkinScan.status == "completed"
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
    today = datetime.now(KST).date()
    metric_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == persona_id, DailyMetric.metric_date == today
        )
    )
    metric = metric_result.scalar_one_or_none()

    scan_result = await db.execute(
        select(SkinScan)
        .where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
        .order_by(SkinScan.captured_at.desc())
        .limit(1)
    )
    latest_scan = scan_result.scalar_one_or_none()

    return compute_risk(
        sleep_hours=metric.sleep_hours if metric else None,
        diet_flag=metric.diet_flag if metric else None,
        latest_scores=latest_scan.scores if latest_scan else None,
    )


async def _load_owned_cosmetics(db: AsyncSession, persona_id: str) -> list[PersonaCosmetic]:
    result = await db.execute(
        select(PersonaCosmetic).where(
            PersonaCosmetic.persona_id == persona_id, PersonaCosmetic.deleted_at.is_(None)
        )
    )
    return list(result.scalars())


async def build_chat_reply(db: AsyncSession, persona_id: str, message: str) -> dict:
    """Rule-based SOS 챗봇 응답 — 기능명세서_chatbot.md 9·13절, API명세서.md 15.2절 확정 응답.

    LLM은 호출하지 않는다(10절 LLM 사용 최소화 정책). 파싱은 키워드·별칭 사전, 답변은
    서버 템플릿 치환만으로 조립한다.
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
        }

    owned = await _load_owned_cosmetics(db, persona_id)
    mentions_retinol = _mentions_any(message, RETINOL_ALIASES)
    mentions_vitamin_c = _mentions_any(message, VITAMIN_C_ALIASES)

    # 9절 규칙 예시: 레티놀+비타민C 조합은 승인된 상호작용 규칙(avoid_same_routine)만 사용한다.
    if mentions_retinol and mentions_vitamin_c:
        retinol_product = _owns_ingredient(owned, RETINOL_ALIASES)
        vitamin_c_product = _owns_ingredient(owned, VITAMIN_C_ALIASES)
        if retinol_product and vitamin_c_product:
            reply = (
                f"{_product_label(retinol_product)}와(과) {_product_label(vitamin_c_product)}는 "
                "같은 루틴에서 함께 사용하면 자극 가능성이 있어요. 아침·저녁으로 나누어 "
                "사용해 보세요."
            )
            referenced = [str(retinol_product.id), str(vitamin_c_product.id)]
        else:
            reply = (
                "레티놀과 비타민C 조합은 자극 가능성이 있는 조합으로 분류돼요. 등록된 "
                "화장품에서 두 성분을 모두 확인하지 못해 함께 사용해도 안전하다고 단정할 수 "
                "없어요. My Shelf에 성분을 등록하면 더 정확히 안내할 수 있어요."
            )
            referenced = [str(c.id) for c in (retinol_product, vitamin_c_product) if c]
        return _answer(
            reply,
            faq_id="faq_retinol_vitaminc_combo",
            version=1,
            match_score=0.9,
            referenced=referenced,
            used_contexts=["owned_products"],
            decision={"rule_id": "rule_retinol_vitaminc_avoid", "code": "AVOID_SAME_ROUTINE"},
        )

    # 9절 규칙 예시: 레티놀 보유 + 고위험이면 오늘 사용을 생략하고 진정/보습 대체 제품을 찾는다.
    if mentions_retinol:
        retinol_product = _owns_ingredient(owned, RETINOL_ALIASES)
        if retinol_product is None:
            return _answer(
                "등록된 화장품에서 레티놀 제품을 확인하지 못했어요. My Shelf에 제품을 등록하면 "
                "성분과 오늘 피부 상태를 함께 확인해 안내할 수 있어요.",
                faq_id="faq_retinol_today",
                version=1,
                match_score=0.85,
                referenced=[],
                used_contexts=["owned_products"],
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
        )

    resolved = resolve_faq(message)
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
    }
