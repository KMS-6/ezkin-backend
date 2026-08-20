from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Generation(TimestampMixin, Base):
    """Tracks a generated Report/Briefing/SOS-message id for feedback ownership checks."""

    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    persona_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30))
