from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SkinScan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skin_scans"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    capture_method: Mapped[str] = mapped_column(String(20))
    image_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lighting_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="processing")
    lower_accuracy: Mapped[bool] = mapped_column(Boolean, default=False)

    redness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dryness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    oiliness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    redness_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    dryness_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    oiliness_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    idempotency_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    questionnaire_answers: Mapped["SkinQuestionnaireAnswers | None"] = relationship(
        back_populates="scan", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def scores(self) -> dict | None:
        if (
            self.redness_score is None
            and self.dryness_score is None
            and self.oiliness_score is None
        ):
            return None
        values = {
            "redness": self.redness_score,
            "dryness": self.dryness_score,
            "oiliness": self.oiliness_score,
        }
        return {key: value for key, value in values.items() if value is not None}

    @scores.setter
    def scores(self, value: dict | None) -> None:
        value = value or {}
        self.redness_score = value.get("redness", value.get("flushing"))
        self.dryness_score = value.get("dryness", value.get("moisture"))
        self.oiliness_score = value.get("oiliness")

    @property
    def confidence(self) -> dict | None:
        if all(
            v is None
            for v in (self.redness_confidence, self.dryness_confidence, self.oiliness_confidence)
        ):
            return None
        return {
            "redness": self.redness_confidence,
            "dryness": self.dryness_confidence,
            "oiliness": self.oiliness_confidence,
        }

    @confidence.setter
    def confidence(self, value: dict | None) -> None:
        value = value or {}
        self.redness_confidence = value.get("redness")
        self.dryness_confidence = value.get("dryness")
        self.oiliness_confidence = value.get("oiliness")

    @property
    def failure(self) -> dict | None:
        if self.failure_code is None:
            return None
        return {"code": self.failure_code, "retryable": self.failure_retryable}


class SkinQuestionnaireAnswers(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skin_questionnaire_answers"

    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("skin_scans.id", ondelete="CASCADE"), unique=True, index=True
    )
    questionnaire_version: Mapped[str] = mapped_column(String(20))
    answers: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    scan: Mapped["SkinScan"] = relationship(back_populates="questionnaire_answers")
