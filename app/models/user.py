from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(50))

    cosmetics: Mapped[list["Cosmetic"]] = relationship(back_populates="user")  # noqa: F821
