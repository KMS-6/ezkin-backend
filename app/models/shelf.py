from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Cosmetic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cosmetics"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand: Mapped[str] = mapped_column(String(100))
    product_name: Mapped[str] = mapped_column(String(200))
    product_type: Mapped[str] = mapped_column(String(30))
    ingredients_raw: Mapped[list[str] | None] = mapped_column(JSON)
    image_key: Mapped[str | None] = mapped_column(String(500))
    registration_source: Mapped[str] = mapped_column(String(20), default="manual")
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    user_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped["User"] = relationship(back_populates="cosmetics")
