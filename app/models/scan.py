from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SkinScan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skin_scans"

    persona_id: Mapped[str] = mapped_column(String(60), index=True)
    capture_method: Mapped[str] = mapped_column(String(20))  # "camera" | "questionnaire"
    status: Mapped[str] = mapped_column(String(20), default="processing")
    lower_accuracy: Mapped[bool] = mapped_column(Boolean, default=False)

    # 카메라 스캔 시 저장 경로 (선택)
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 문진 답변 원본 JSON (선택)
    questionnaire_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 결과 점수 JSON {"redness": 0.3, "dryness": 0.0, "oiliness": 0.6} (선택)
    scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 실패 정보 JSON {"code": ..., "message": ..., "retryable": false} (선택)
    failure: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Idempotency-Key 헤더값 저장 (중복 제출 방지)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    idempotency_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
