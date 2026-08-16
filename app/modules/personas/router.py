from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_availability import compute_feature_availability
from app.core.mock_persona import list_personas
from app.db.session import get_db
from app.models.persona import Persona
from app.modules.personas.schemas import (
    PersonaDetailResponse,
    PersonaListResponse,
    PersonaSummary,
)

router = APIRouter(prefix="/personas", tags=["personas"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PersonaListResponse)
async def get_personas(db: DbSession) -> PersonaListResponse:
    personas = await list_personas(db)
    return PersonaListResponse(
        personas=[
            PersonaSummary(id=p.id, label=p.label, summary_traits=p.summary_traits)
            for p in personas
        ]
    )


@router.get("/{persona_id}", response_model=PersonaDetailResponse)
async def get_persona_detail(persona_id: str, db: DbSession) -> PersonaDetailResponse:
    persona = await db.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="등록되지 않은 페르소나입니다."
        )
    features = await compute_feature_availability(db, persona.id)
    return PersonaDetailResponse(
        id=persona.id,
        label=persona.label,
        summary_traits=persona.summary_traits,
        features=features,
    )
