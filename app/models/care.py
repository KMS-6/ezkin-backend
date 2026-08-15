from datetime import date
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CareContext(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "care_contexts"
    __table_args__ = (UniqueConstraint("user_id", "context_date"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    context_date: Mapped[date] = mapped_column(Date)
    care_mode: Mapped[str] = mapped_column(String(30))
    observed_factors: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    ruleset_version: Mapped[str] = mapped_column(String(30))


class CareRoutine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "care_routines"
    __table_args__ = (UniqueConstraint("care_context_id", "time_of_day"),)

    care_context_id: Mapped[UUID] = mapped_column(
        ForeignKey("care_contexts.id", ondelete="CASCADE"), index=True
    )
    time_of_day: Mapped[str] = mapped_column(String(20))
    generated_text: Mapped[str | None] = mapped_column(Text)
    generation_source: Mapped[str] = mapped_column(String(30))


class RoutineStep(
    UUIDPrimaryKeyMixin, Base
):  # 타임스탬프 없음: 루틴 cascade 삭제로만 생명주기 관리
    __tablename__ = "routine_steps"
    __table_args__ = (
        UniqueConstraint("routine_id", "step_order"),
        CheckConstraint("step_order > 0", name="positive_step_order"),
    )

    routine_id: Mapped[UUID] = mapped_column(
        ForeignKey("care_routines.id", ondelete="CASCADE"), index=True
    )
    cosmetic_id: Mapped[UUID] = mapped_column(
        ForeignKey("cosmetics.id", ondelete="RESTRICT"), index=True
    )
    step_order: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100))
    amount_hint: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)
    caution_note: Mapped[str | None] = mapped_column(Text)
    product_name_snapshot: Mapped[str] = mapped_column(String(200))
