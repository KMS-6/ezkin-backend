# report 브랜치 전용 최소 정의 — scan 브랜치 병합 시 교체
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SkinScan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skin_scans"

    persona_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    capture_method: Mapped[str] = mapped_column(String(20), nullable=False, default="camera")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lower_accuracy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
