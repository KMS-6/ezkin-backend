from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SosSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sos_sessions"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )


class SosMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sos_messages"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sos_sessions.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    message: Mapped[str] = mapped_column(String(1000))
    reply_type: Mapped[str] = mapped_column(String(20))
    reply: Mapped[str] = mapped_column(String(1000))
    matched_faq: Mapped[dict | None] = mapped_column(JSON)
    decision: Mapped[dict | None] = mapped_column(JSON)
    referenced_cosmetic_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    used_contexts: Mapped[list[str]] = mapped_column(JSON, default=list)
    safety_flag: Mapped[str | None] = mapped_column(String(50))
    expert_referral_suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    # 18.1절 로깅 권장 항목(파싱 방식) 최소 버전 — 응답 스키마에는 노출하지 않고 내부
    # 관측(rule-only 처리율 등, 18.3절)에만 사용한다.
    intent: Mapped[str | None] = mapped_column(String(30))
    parse_confidence: Mapped[float | None] = mapped_column(Float)
