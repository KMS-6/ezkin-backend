from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Persona(TimestampMixin, Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    summary_traits: Mapped[dict] = mapped_column(JSON)
    # "no_watch" | "has_watch" — spec Mock Persona 데이터 생성 규칙
    watch_status: Mapped[str] = mapped_column(String(20), server_default="no_watch")
