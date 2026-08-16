from datetime import date, datetime

from pydantic import BaseModel


class RoutineStep(BaseModel):
    order: int
    action: str = "use"
    cosmetic_id: str
    name: str
    note: str | None = None


class PrescriptionOut(BaseModel):
    date: date
    steps: list[RoutineStep]
    avoid: list[str]
    disclaimer: str


class NotificationSettingsIn(BaseModel):
    morning_briefing_enabled: bool


class NotificationSettingsOut(BaseModel):
    morning_briefing_enabled: bool
    updated_at: datetime
