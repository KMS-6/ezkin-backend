from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendation_products"
    __table_args__ = (UniqueConstraint("brand", "name"),)

    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50))
    external_url: Mapped[str] = mapped_column(String(500))
    safety_policy_note: Mapped[str | None] = mapped_column(String(300))
