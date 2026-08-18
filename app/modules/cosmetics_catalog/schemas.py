from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ProductType(StrEnum):
    CLEANSER = "cleanser"
    TONER = "toner"
    SERUM = "serum"
    MOISTURIZER = "moisturizer"
    SUNSCREEN = "sunscreen"
    MASK = "mask"


class RiskLevel(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"


class RiskAlert(BaseModel):
    ingredient: str
    risk_level: str
    target_concern: str


class CosmeticCreateResult(BaseModel):
    cosmetic_id: str
    matched_ingredients: list[str]
    risk_alerts: list[RiskAlert]


class CosmeticOut(BaseModel):
    cosmetic_id: str
    brand: str
    product_name: str
    product_type: str | None
    ingredients_raw: list[str] | None
    updated_at: datetime


class CosmeticListResponse(BaseModel):
    items: list[CosmeticOut]


class CosmeticUpdateIn(BaseModel):
    brand: str | None = None
    product_name: str | None = None
    product_type: ProductType | None = None
    ingredients_raw: list[str] | None = None


class IngredientOut(BaseModel):
    id: str
    name: str
    risk_level: str
    target_concern: str | None
    description: str | None


class IngredientListResponse(BaseModel):
    ingredients: list[IngredientOut]


class IngredientCreateIn(BaseModel):
    name: str
    risk_level: RiskLevel
    target_concern: str | None = None
    description: str | None = None
