import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import Briefing
from app.models.cosmetic_catalog import PersonaCosmetic
from app.models.generation import Generation
from app.modules.cosmetics_catalog.matching import match_ingredient_risks
from app.modules.risk.logic import load_today_risk_context

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


def _product_type_rank(product_type: str | None) -> int:
    if product_type in PRODUCT_TYPE_ORDER:
        return PRODUCT_TYPE_ORDER.index(product_type)
    return len(PRODUCT_TYPE_ORDER)


async def build_routine(
    db: AsyncSession, persona_id: str, risk_level: str
) -> tuple[list[dict], list[dict]]:
    result = await db.execute(
        select(PersonaCosmetic).where(
            PersonaCosmetic.persona_id == persona_id, PersonaCosmetic.deleted_at.is_(None)
        )
    )
    cosmetics = sorted(result.scalars(), key=lambda c: _product_type_rank(c.product_type))

    high_risk_day = risk_level in {"high", "very_high"}
    routine: list[dict] = []
    skip: list[dict] = []
    order = 1
    for cosmetic in cosmetics:
        name = f"{cosmetic.brand} {cosmetic.product_name}"
        _, risk_alerts = await match_ingredient_risks(db, cosmetic.ingredients_raw)
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
                "note": None,
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

    summary = (
        ", ".join(text for _, text in factors)
        if factors
        else "특별한 위험 요인이 관찰되지 않았어요."
    )
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
        common_knowledge=None,
        data_coverage=data_coverage,
        limitation_notice=limitation_notice,
        generated_at=now_kst,
        sent_at=now_kst,
    )
    db.add(briefing)
    await db.flush()
    db.add(Generation(id=briefing.generation_id, persona_id=persona_id, kind="briefing"))
    await db.commit()
    return briefing
