from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Consent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("persona_id", "type"),)

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30))
    consented: Mapped[bool] = mapped_column(Boolean, default=False)


class OnboardingProfile(TimestampMixin, Base):
    __tablename__ = "onboarding_profiles"

    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), primary_key=True
    )
    skin_concern_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    menstrual_cycle_tracking: Mapped[bool | None] = mapped_column(Boolean)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    # ADR 003: 기상청 API 조회용 위치. 위도/경도가 없으면 weather 모듈이
    # 서울 기본 좌표로 폴백한다.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
