from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductType(StrEnum):
    CLEANSER = "cleanser"
    TONER = "toner"
    SERUM = "serum"
    MOISTURIZER = "moisturizer"
    SUNSCREEN = "sunscreen"
    MASK = "mask"


class RegistrationSource(StrEnum):
    MANUAL = "manual"
    IMAGE_SCAN = "image_scan"


class ShelfProductCreate(BaseModel):
    brand: str = Field(min_length=1, max_length=100)
    product_name: str = Field(min_length=1, max_length=200)
    product_type: ProductType
    ingredients_raw: list[str] | None = None
    image_key: str | None = Field(default=None, max_length=500)
    registration_source: RegistrationSource = RegistrationSource.MANUAL
    opened_at: date | None = None
    expires_at: date | None = None


class ShelfProductUpdate(BaseModel):
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    product_name: str | None = Field(default=None, min_length=1, max_length=200)
    product_type: ProductType | None = None
    ingredients_raw: list[str] | None = None
    opened_at: date | None = None
    expires_at: date | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_string_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("brand", "product_name"):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be set to null")
        return data


class ShelfProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand: str
    product_name: str
    product_type: str
    ingredients_raw: list[str] | None
    image_key: str | None
    registration_source: str
    user_verified_at: datetime | None
    opened_at: date | None
    expires_at: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ShelfProductListResponse(BaseModel):
    items: list[ShelfProductResponse]
