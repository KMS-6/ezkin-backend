from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SkinScan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skin_scans"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    capture_method: Mapped[str] = mapped_column(String(20))
    image_key: Mapped[str | None] = mapped_column(String(500))
    questionnaire_version: Mapped[str | None] = mapped_column(String(10))
    answers: Mapped[list[dict] | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lighting_ok: Mapped[bool | None] = mapped_column(Boolean)

    status: Mapped[str] = mapped_column(String(20), default="processing")
    lower_accuracy: Mapped[bool] = mapped_column(Boolean, default=False)
    scores: Mapped[dict[str, float] | None] = mapped_column(JSON)
    confidence: Mapped[dict[str, float] | None] = mapped_column(JSON)
    delta_vs_baseline: Mapped[dict[str, float] | None] = mapped_column(JSON)
    delta_vs_previous: Mapped[dict[str, float] | None] = mapped_column(JSON)
    limitation_notice: Mapped[str | None] = mapped_column(String(300))
    failure_code: Mapped[str | None] = mapped_column(String(50))
    failure_message: Mapped[str | None] = mapped_column(String(300))
    failure_retryable: Mapped[bool | None] = mapped_column(Boolean)
    analysis_provider: Mapped[str | None] = mapped_column(String(50))
    analysis_model: Mapped[str | None] = mapped_column(String(100))
    analysis_model_version: Mapped[str | None] = mapped_column(String(50))
    analysis_schema_version: Mapped[str | None] = mapped_column(String(50))
