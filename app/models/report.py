from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    period_days: Mapped[int] = mapped_column(Integer)
    end_date: Mapped[date] = mapped_column(Date)
    locale: Mapped[str] = mapped_column(String(10), default="ko-KR")
    status: Mapped[str] = mapped_column(String(20), default="processing")
    period: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(String(500))
    observations: Mapped[list[dict] | None] = mapped_column(JSON)
    patterns: Mapped[list[dict] | None] = mapped_column(JSON)
    recommendations: Mapped[list[dict] | None] = mapped_column(JSON)
    limitations: Mapped[str | None] = mapped_column(String(300))
    safety_status: Mapped[str | None] = mapped_column(String(20))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
