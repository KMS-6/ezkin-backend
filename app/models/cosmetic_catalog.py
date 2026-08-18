from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PersonaCosmetic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The `/cosmetics` resource from API명세서.md — owned by a mock persona.

    Distinct from `app.models.shelf.Cosmetic`, which backs the already-shipped
    `/api/v1/shelf/products` feature owned by a real Bearer-token user.
    """

    __tablename__ = "persona_cosmetics"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    image_key: Mapped[str | None] = mapped_column(String(500))
    brand: Mapped[str] = mapped_column(String(100))
    product_name: Mapped[str] = mapped_column(String(200))
    product_type: Mapped[str | None] = mapped_column(String(30))
    ingredients_raw: Mapped[list[str] | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Ingredient(TimestampMixin, Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    risk_level: Mapped[str] = mapped_column(String(10))
    target_concern: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
