from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeatherSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """기능명세서_briefing.md 4.1절 날씨 데이터.

    외부 날씨 API 연동은 MVP 범위 밖이라 이 테이블에 행이 없으면 위험도·브리핑
    계산은 날씨 요인을 조용히 생략한다(임의 날씨 생성 금지, 4.1절).
    """

    __tablename__ = "weather_snapshots"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_percent: Mapped[float | None] = mapped_column(Float)
    uv_index: Mapped[float | None] = mapped_column(Float)
    weather_condition: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(50))
