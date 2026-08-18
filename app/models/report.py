from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DailyMetrics(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """날짜별 집계 지표 — scan 결과에서 파생된 일일 요약"""

    __tablename__ = "daily_metrics"

    persona_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    avg_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """14일/30일 기간 리포트"""

    __tablename__ = "reports"

    persona_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safety_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
