from pydantic import BaseModel

from app.models.persona import WatchStatus


class FeatureAvailability(BaseModel):
    feature: str
    status: str
    reason: str | None = None
    fallback: str | None = None


class PersonaSummary(BaseModel):
    id: str
    label: str
    summary_traits: dict


class PersonaListResponse(BaseModel):
    personas: list[PersonaSummary]


class PersonaDetailResponse(PersonaSummary):
    watch_status: WatchStatus
    features: list[FeatureAvailability]
