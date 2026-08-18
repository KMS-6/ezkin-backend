from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WaterIntakeLevel(StrEnum):
    UNDER_3_GLASSES = "under_3_glasses"
    THREE_TO_FIVE_GLASSES = "three_to_five_glasses"
    OVER_5_GLASSES = "over_5_glasses"


class DietFlag(StrEnum):
    NORMAL = "normal"
    SPICY = "spicy"
    LATE_NIGHT_MEAL = "late_night_meal"


class HealthDataIn(BaseModel):
    user_token: str
    metric_date: date
    sleep_hours: float | None = Field(default=None, ge=0)
    hrv_ms: float | None = Field(default=None, ge=0)
    active_energy_kcal: float | None = Field(default=None, ge=0)


class HealthDataReceived(BaseModel):
    received: bool = True


class DailyMetricIn(BaseModel):
    metric_date: date
    water_intake_level: WaterIntakeLevel
    diet_flag: DietFlag | None = None


class DailyMetricOut(BaseModel):
    metric_date: date
    water_intake_level: str | None
    diet_flag: str | None
    updated_at: datetime | None
