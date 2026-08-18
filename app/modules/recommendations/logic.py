from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import OnboardingProfile
from app.models.recommendation import Product
from app.models.scan import SkinScan

CONCERN_TO_CATEGORY = {
    "cn_dryness": "moisturizer",
    "cn_oily_tzone": "toner",
    "cn_acne": "serum",
    "cn_hormonal": "serum",
}
METRIC_TO_CATEGORY = {
    "dryness": "moisturizer",
    "redness": "serum",
    "oiliness": "toner",
}
ELEVATED_THRESHOLD = 0.66


async def build_recommendations(db: AsyncSession, persona_id: str) -> list[dict]:
    """Rule-based matching against onboarding concerns and the latest scan's elevated metrics."""
    categories: set[str] = set()
    reasons: dict[str, str] = {}

    profile = await db.get(OnboardingProfile, persona_id)
    if profile:
        for concern_id in profile.skin_concern_ids or []:
            category = CONCERN_TO_CATEGORY.get(concern_id)
            if category:
                categories.add(category)
                reasons[category] = "온보딩에서 선택한 피부 고민과 연관된 제품이에요."

    scan_result = await db.execute(
        select(SkinScan)
        .where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
        .order_by(SkinScan.captured_at.desc())
        .limit(1)
    )
    latest_scan = scan_result.scalar_one_or_none()
    if latest_scan and latest_scan.scores:
        for metric, value in latest_scan.scores.items():
            if value >= ELEVATED_THRESHOLD:
                category = METRIC_TO_CATEGORY.get(metric)
                if category:
                    categories.add(category)
                    reasons[category] = f"최근 스캔에서 {metric} 수치가 높게 관찰돼 추천돼요."

    stmt = select(Product)
    if categories:
        stmt = stmt.where(Product.category.in_(categories))
    result = await db.execute(stmt)

    return [
        {
            "product_id": str(product.id),
            "name": product.name,
            "reason": reasons.get(product.category, "현재 맥락에서 참고할 수 있는 제품이에요."),
            "external_url": product.external_url,
        }
        for product in result.scalars()
    ]
