from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GenerationFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_feedback"

    generation_id: Mapped[str] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[str] = mapped_column(String(20))
    reason_code: Mapped[str | None] = mapped_column(String(40))
    comment: Mapped[str | None] = mapped_column(String(1000))
