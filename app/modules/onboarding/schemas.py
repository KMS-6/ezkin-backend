from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.personas.schemas import FeatureAvailability


class SkinConcern(BaseModel):
    id: str
    label: str


class SkinConcernListResponse(BaseModel):
    concerns: list[SkinConcern]


class OnboardingProfileIn(BaseModel):
    skin_concern_ids: list[str] = Field(default_factory=list)
    birth_year: int | None = None
    menstrual_cycle_tracking: bool | None = None
    latitude: float | None = None
    longitude: float | None = None


class OnboardingProfileResponse(BaseModel):
    onboarding_completed: bool


class ConsentOut(BaseModel):
    type: str
    consented: bool
    updated_at: datetime | None


class ConsentListResponse(BaseModel):
    consents: list[ConsentOut]


class ConsentUpdateIn(BaseModel):
    consented: bool


class FeatureAvailabilityListResponse(BaseModel):
    features: list[FeatureAvailability]
