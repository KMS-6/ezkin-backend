from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
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
