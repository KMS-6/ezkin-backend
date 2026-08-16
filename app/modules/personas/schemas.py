from pydantic import BaseModel


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
    features: list[FeatureAvailability]
