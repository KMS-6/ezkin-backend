from enum import StrEnum

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WatchStatus(StrEnum):
    NO_WATCH = "no_watch"
    HAS_WATCH = "has_watch"


class Persona(TimestampMixin, Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    summary_traits: Mapped[dict] = mapped_column(JSON)
    watch_status: Mapped[str] = mapped_column(String(20), server_default=WatchStatus.NO_WATCH)
