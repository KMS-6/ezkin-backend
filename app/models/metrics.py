from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DailyMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("persona_id", "metric_date"),)

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    metric_date: Mapped[date] = mapped_column(Date)
    water_intake_level: Mapped[str | None] = mapped_column(String(20))
    diet_flag: Mapped[str | None] = mapped_column(String(30))
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    hrv_ms: Mapped[float | None] = mapped_column(Float)
    active_energy_kcal: Mapped[float | None] = mapped_column(Float)
