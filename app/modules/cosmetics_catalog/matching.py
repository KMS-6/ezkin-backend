from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cosmetic_catalog import Ingredient


def normalize(text: str) -> str:
    return " ".join(text.strip().split())


async def load_ingredient_catalog(db: AsyncSession) -> list[Ingredient]:
    """Fetch the full ingredient catalog once, for callers matching in a loop."""
    result = await db.execute(select(Ingredient))
    return list(result.scalars())


def match_ingredient_risks(
    ingredients_raw: list[str] | None, catalog: list[Ingredient]
) -> tuple[list[str], list[dict]]:
    """Deterministic normalized-name matching against a pre-loaded ingredient catalog.

    Returns (matched_ingredient_ids, risk_alerts) — risk_alerts only includes
    catalog entries whose risk_level is "caution".
    """
    if not ingredients_raw:
        return [], []

    normalized_inputs = {normalize(item) for item in ingredients_raw}

    matched_ids: list[str] = []
    risk_alerts: list[dict] = []
    for ingredient in catalog:
        if normalize(ingredient.name) not in normalized_inputs:
            continue
        matched_ids.append(ingredient.id)
        if ingredient.risk_level == "caution":
            risk_alerts.append(
                {
                    "ingredient": ingredient.name,
                    "risk_level": ingredient.risk_level,
                    "target_concern": ingredient.target_concern or "",
                }
            )
    return matched_ids, risk_alerts
