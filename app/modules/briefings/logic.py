import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import Briefing
from app.models.cosmetic_catalog import PersonaCosmetic
from app.models.generation import Generation
from app.modules.briefings.narration import narrate_briefing
from app.modules.cosmetics_catalog.matching import load_ingredient_catalog, match_ingredient_risks
from app.modules.knowledge.matching import find_claim
from app.modules.risk.logic import (
    LOW_HUMIDITY_THRESHOLD,
    SLEEP_LOW_THRESHOLD_HOURS,
    load_today_risk_context,
)

KST = ZoneInfo("Asia/Seoul")
NO_COSMETICS_NOTICE = (
    "등록된 화장품이 없어 일반적인 관리 방법만 안내해요. My Shelf에 제품을 등록하면 더 "
    "구체적으로 안내할 수 있어요."
)
NO_FITTING_COSMETIC_NOTICE = (
    "오늘 조건에 맞는 등록 제품을 확인하기 어려워요. 일반적인 관리 방법을 참고해 주세요."
)
LIMITED_ACCURACY_NOTICE = " HRV 데이터가 충분히 쌓이지 않아 정확도가 제한된 상태예요."
BRIEFING_READY_TIME = time(6, 30)
PRODUCT_TYPE_ORDER = ["cleanser", "toner", "serum", "moisturizer", "sunscreen", "mask"]

# 8.1절 예시의 note 문구를 기준으로 한 제품타입별 사용법 안내. 고위험일에는 조금 더
# 신경써서 바르라는 조언으로 갈라지되, 횟수·강도를 정밀하게 단정하지 않는 일반적인 사용
# 팁 수준으로 제한한다(효능·성분을 확정하지 않는다는 13.4절 원칙과 동일한 정신).
ROUTINE_NOTES: dict[str, dict[bool, str | None]] = {
    "cleanser": {True: "미온수로 자극 없이 부드럽게 세안해 주세요.", False: None},
    "toner": {True: "자극을 줄이도록 겹겹이 얇게 발라 주세요.", False: "얇게 사용해 주세요."},
    "serum": {True: "소량만 사용해 주세요.", False: None},
    "moisturizer": {
        True: "수분 손실을 막기 위해 평소보다 두껍게 발라 주세요.",
        False: "보습을 마무리해 주세요.",
    },
    "sunscreen": {True: None, False: None},
    "mask": {True: "자극 가능성이 있어 짧게 사용해 주세요.", False: None},
}


# 6.1절 가중치와 동일(risk/logic.py::compute_risk) — 근거는 Rule Engine이 실제로
# 가장 무겁게 반영한 조건에만 붙인다(8.3절: "가중치가 가장 높은 조건 하나에 대해서만").
_FACTOR_WEIGHT = {"sleep": 2, "hrv": 2, "weather": 1, "scan": 2, "diet": 1}


def _top_factor(factors: list[tuple[str, str]]) -> tuple[str, str] | None:
    if not factors:
        return None
    # max()는 동점일 때 먼저 나온 항목을 유지한다 — compute_risk의 검사 순서
    # (sleep→hrv→uv→humidity→scan→diet)가 곧 동점 시 우선순위가 된다.
    return max(factors, key=lambda factor: _FACTOR_WEIGHT.get(factor[0], 0))


async def select_common_knowledge(db: AsyncSession, context: dict) -> dict | None:
    """오늘 Rule Engine이 트리거한 최우선 조건 하나에 대해서만 승인된 공통 지식
    근거를 찾는다(8.3절). sleep·humidity 외 조건은 아직 대응하는 Claim Card 매핑이
    없어(RAG 문서에 예시가 없음) 항상 None이다.
    """
    top = _top_factor(context["factors"])
    if top is None:
        return None
    factor_type, factor_text = top

    if factor_type == "sleep":
        metric = context["metric"]
        facts: set[str] = set()
        if metric and metric.sleep_hours is not None:
            facts.add("sleep_hours_available")
            if metric.sleep_hours < SLEEP_LOW_THRESHOLD_HOURS:
                facts.add("sleep_below_personal_baseline_or_threshold")
        topic = "sleep"
    elif factor_type == "weather" and "습도" in factor_text:
        weather = context["weather"]
        facts = set()
        if context["weather_consented"]:
            facts.add("weather_consent")
        if weather is not None:
            facts.add("fresh_humidity_data")
            if weather.humidity_percent is not None and weather.humidity_percent < (
                LOW_HUMIDITY_THRESHOLD
            ):
                facts.add("humidity_below_rule_threshold")
        topic = "humidity"
    else:
        return None

    claim = await find_claim(db, feature="briefing", topic=topic, facts=facts)
    if claim is None:
        return None
    return {"claim_id": claim.claim_id, "version": claim.version, "sentence": claim.sentence}


def _product_type_rank(product_type: str | None) -> int:
    if product_type in PRODUCT_TYPE_ORDER:
        return PRODUCT_TYPE_ORDER.index(product_type)
    return len(PRODUCT_TYPE_ORDER)


def _routine_note(product_type: str | None, high_risk_day: bool) -> str | None:
    templates = ROUTINE_NOTES.get(product_type or "")
    if templates is None:
        return None
    return templates[high_risk_day]


async def build_routine(
    db: AsyncSession, persona_id: str, risk_level: str
) -> tuple[list[dict], list[dict]]:
    result = await db.execute(
        select(PersonaCosmetic).where(
            PersonaCosmetic.persona_id == persona_id, PersonaCosmetic.deleted_at.is_(None)
        )
    )
    cosmetics = sorted(result.scalars(), key=lambda c: _product_type_rank(c.product_type))
    catalog = await load_ingredient_catalog(db)

    high_risk_day = risk_level in {"high", "very_high"}
    routine: list[dict] = []
    skip: list[dict] = []
    order = 1
    for cosmetic in cosmetics:
        name = f"{cosmetic.brand} {cosmetic.product_name}"
        _, risk_alerts = match_ingredient_risks(cosmetic.ingredients_raw, catalog)
        if high_risk_day and risk_alerts:
            caution_names = ", ".join(alert["ingredient"] for alert in risk_alerts)
            skip.append(
                {
                    "cosmetic_id": str(cosmetic.id),
                    "name": name,
                    "reason": f"자극 가능성 낮추려면 {caution_names} 성분 제품은 오늘 쉬어보세요.",
                }
            )
            continue
        routine.append(
            {
                "order": order,
                "action": "use",
                "cosmetic_id": str(cosmetic.id),
                "name": name,
                "note": _routine_note(cosmetic.product_type, high_risk_day),
            }
        )
        order += 1
    return routine, skip


async def get_or_generate_briefing(db: AsyncSession, persona_id: str) -> Briefing | None:
    """Return today's Briefing if it exists or the ready-time has passed; else None (pending)."""
    now_kst = datetime.now(KST)
    today = now_kst.date()

    existing = await db.execute(
        select(Briefing).where(Briefing.persona_id == persona_id, Briefing.briefing_date == today)
    )
    briefing = existing.scalar_one_or_none()
    if briefing is not None:
        return briefing

    ready_at = datetime.combine(today, BRIEFING_READY_TIME, tzinfo=KST)
    if now_kst < ready_at:
        return None

    context = await load_today_risk_context(db, persona_id, today, now_kst)
    risk_level = context["risk_level"]
    factors = context["factors"]
    routine, skip = await build_routine(db, persona_id, risk_level)
    common_knowledge = await select_common_knowledge(db, context)

    metric = context["metric"]
    watch_used = bool(metric and (metric.sleep_hours is not None or metric.hrv_ms is not None))
    data_coverage = {
        "weather": context["weather"] is not None,
        "watch": watch_used,
        "skin_scan": context["latest_scan"] is not None,
        "my_shelf": bool(routine or skip),
        "baseline_established": context["baseline_established"],
    }

    if not data_coverage["my_shelf"]:
        shelf_notice = NO_COSMETICS_NOTICE
    elif not routine:
        shelf_notice = NO_FITTING_COSMETIC_NOTICE
    else:
        shelf_notice = None

    base_summary = (
        ", ".join(text for _, text in factors)
        if factors
        else "특별한 위험 요인이 관찰되지 않았어요."
    )
    narrated_summary = await narrate_briefing(factors, common_knowledge)
    summary = narrated_summary or base_summary
    if shelf_notice:
        summary = f"{summary} {shelf_notice}"

    limitation_notice = "의료적 진단이 아닌 생활·환경 데이터 기반 참고 안내입니다."
    if not data_coverage["baseline_established"]:
        limitation_notice += LIMITED_ACCURACY_NOTICE

    briefing = Briefing(
        persona_id=persona_id,
        briefing_date=today,
        generation_id=str(uuid.uuid4()),
        risk_level=risk_level,
        headline=(
            "오늘은 평온한 컨디션이 예상돼요."
            if risk_level == "low"
            else "오늘은 피부 자극에 주의해 주세요."
        ),
        summary=summary,
        contributing_factors=[{"type": t, "text": text} for t, text in factors],
        routine=routine,
        skip=skip,
        common_knowledge=common_knowledge,
        data_coverage=data_coverage,
        limitation_notice=limitation_notice,
        generated_at=now_kst,
        sent_at=now_kst,
    )
    db.add(briefing)
    try:
        await db.flush()
        db.add(Generation(id=briefing.generation_id, persona_id=persona_id, kind="briefing"))
        await db.commit()
    except IntegrityError:
        # Concurrent request for the same persona/day won the race and already
        # committed a briefing; replay that one instead of 500ing.
        await db.rollback()
        existing = await db.execute(
            select(Briefing).where(
                Briefing.persona_id == persona_id, Briefing.briefing_date == today
            )
        )
        return existing.scalar_one_or_none()
    return briefing
