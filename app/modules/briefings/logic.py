import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import Briefing
from app.models.cosmetic_catalog import PersonaCosmetic
from app.models.generation import Generation
from app.models.metrics import DailyMetric
from app.models.onboarding import Consent
from app.models.skin_scan import SkinScan
from app.modules.cosmetics_catalog.matching import match_ingredient_risks
from app.modules.risk.logic import compute_risk

KST = ZoneInfo("Asia/Seoul")
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

    risk_level, factors = compute_risk(
        sleep_hours=metric.sleep_hours if metric else None,
        diet_flag=metric.diet_flag if metric else None,
        latest_scores=latest_scan.scores if latest_scan else None,
    )
    routine, skip = await build_routine(db, persona_id, risk_level)

    consents_result = await db.execute(select(Consent).where(Consent.persona_id == persona_id))
    consent_map = {c.type: c.consented for c in consents_result.scalars()}

    data_coverage = {
        "weather": consent_map.get("weather_location", False),
        "watch": consent_map.get("apple_health", False),
        "skin_scan": latest_scan is not None,
        "my_shelf": bool(routine or skip),
        "baseline_established": latest_scan is not None,
    }

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
        summary=", ".join(factors) if factors else "특별한 위험 요인이 관찰되지 않았어요.",
        contributing_factors=[{"type": "rule", "text": factor} for factor in factors],
        routine=routine,
        skip=skip,
        common_knowledge=None,
        data_coverage=data_coverage,
        limitation_notice="의료적 진단이 아닌 생활·환경 데이터 기반 참고 안내입니다.",
        generated_at=now_kst,
        sent_at=now_kst,
    )
    db.add(briefing)
    await db.flush()
    db.add(Generation(id=briefing.generation_id, persona_id=persona_id, kind="briefing"))
    await db.commit()
    return briefing
