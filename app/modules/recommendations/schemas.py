from pydantic import BaseModel


class RecommendationOut(BaseModel):
    product_id: str
    name: str
    reason: str
    external_url: str


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationOut]


class ProductCreateIn(BaseModel):
    name: str
    brand: str
    category: str | None = None
    external_url: str
    safety_policy_note: str | None = None


class ProductOut(BaseModel):
    product_id: str
    name: str
    brand: str
    category: str | None
    external_url: str
    safety_policy_note: str | None


class ProductListResponse(BaseModel):
    items: list[ProductOut]
