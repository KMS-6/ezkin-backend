from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_availability import compute_feature_availability
from app.core.mock_persona import get_persona, get_persona_id
from app.db.session import get_db
from app.models.onboarding import Consent, OnboardingProfile
from app.models.persona import Persona
from app.modules.onboarding.schemas import (
    ConsentListResponse,
    ConsentOut,
    ConsentUpdateIn,
    FeatureAvailability,
    FeatureAvailabilityListResponse,
    OnboardingProfileIn,
    OnboardingProfileResponse,
    SkinConcern,
    SkinConcernListResponse,
)

router = APIRouter(tags=["onboarding"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]
PersonaMock = Annotated[Persona, Depends(get_persona)]

SKIN_CONCERNS = [
    {"id": "cn_acne", "label": "트러블·여드름"},
    {"id": "cn_oily_tzone", "label": "T존 유분"},
    {"id": "cn_dryness", "label": "건조·당김"},
    {"id": "cn_hormonal", "label": "생리 전 트러블"},
]

CONSENT_TYPES = ("apple_health", "weather_location")


@router.get("/onboarding/skin-concerns", response_model=SkinConcernListResponse)
async def get_skin_concerns() -> SkinConcernListResponse:
    return SkinConcernListResponse(concerns=[SkinConcern(**c) for c in SKIN_CONCERNS])


@router.post("/onboarding/profile", response_model=OnboardingProfileResponse)
async def save_onboarding_profile(
    payload: OnboardingProfileIn, db: DbSession, persona_id: PersonaId
) -> OnboardingProfileResponse:
    profile = await db.get(OnboardingProfile, persona_id)
    if profile is None:
        profile = OnboardingProfile(persona_id=persona_id)
        db.add(profile)
    profile.skin_concern_ids = payload.skin_concern_ids
    profile.birth_year = payload.birth_year
    profile.menstrual_cycle_tracking = payload.menstrual_cycle_tracking
    profile.onboarding_completed = True
    await db.commit()
    return OnboardingProfileResponse(onboarding_completed=True)


@router.get("/consents", response_model=ConsentListResponse)
async def get_consents(db: DbSession, persona_id: PersonaId) -> ConsentListResponse:
    result = await db.execute(select(Consent).where(Consent.persona_id == persona_id))
    existing = {c.type: c for c in result.scalars()}
    consents = [
        ConsentOut(
            type=consent_type,
            consented=existing[consent_type].consented if consent_type in existing else False,
            updated_at=existing[consent_type].updated_at if consent_type in existing else None,
        )
        for consent_type in CONSENT_TYPES
    ]
    return ConsentListResponse(consents=consents)


@router.put("/consents/{consent_type}", response_model=ConsentOut)
async def update_consent(
    consent_type: str,
    payload: ConsentUpdateIn,
    db: DbSession,
    persona_id: PersonaId,
) -> ConsentOut:
    if consent_type not in CONSENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="지원하지 않는 동의 항목입니다.",
        )
    result = await db.execute(
        select(Consent).where(Consent.persona_id == persona_id, Consent.type == consent_type)
    )
    consent = result.scalar_one_or_none()
    if consent is None:
        consent = Consent(persona_id=persona_id, type=consent_type, consented=payload.consented)
        db.add(consent)
    else:
        consent.consented = payload.consented
    await db.commit()
    await db.refresh(consent)
    return ConsentOut(type=consent.type, consented=consent.consented, updated_at=consent.updated_at)


@router.get("/me/feature-availability", response_model=FeatureAvailabilityListResponse)
async def get_feature_availability(
    db: DbSession, persona: PersonaMock
) -> FeatureAvailabilityListResponse:
    features = await compute_feature_availability(db, persona)
    return FeatureAvailabilityListResponse(
        features=[FeatureAvailability(**feature) for feature in features]
    )
