from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Briefing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "briefings"
    __table_args__ = (UniqueConstraint("persona_id", "briefing_date"),)

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    briefing_date: Mapped[date] = mapped_column(Date)
    generation_id: Mapped[str] = mapped_column(String(64), unique=True)
    risk_level: Mapped[str] = mapped_column(String(20))
    headline: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(500))
    contributing_factors: Mapped[list[dict]] = mapped_column(JSON)
    routine: Mapped[list[dict]] = mapped_column(JSON)
    skip: Mapped[list[dict]] = mapped_column(JSON)
    common_knowledge: Mapped[dict | None] = mapped_column(JSON)
    data_coverage: Mapped[dict[str, bool]] = mapped_column(JSON)
    limitation_notice: Mapped[str] = mapped_column(String(300))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationSettings(TimestampMixin, Base):
    __tablename__ = "notification_settings"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), primary_key=True
    )
    morning_briefing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
