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
    # 10.2절 4단계: 이 메시지의 파싱이 실제로 LLM escalation을 거쳤는지(성공 여부).
    # rule_only_rate(18.3절)를 정확히 계산하려면 confidence 값만으로는 판단할 수
    # 없다 — escalation이 성공하면 parse_confidence가 보정값(0.75)으로 덮어써지기
    # 때문이다.
    llm_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
