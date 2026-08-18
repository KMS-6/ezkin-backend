from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.persona import Persona

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _mock_persona_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="mock_persona_required: 유효한 X-Mock-Persona-Id 헤더가 필요합니다.",
    )


async def get_persona(
    db: DbSession,
    x_mock_persona_id: Annotated[str | None, Header()] = None,
) -> Persona:
    if not x_mock_persona_id:
        raise _mock_persona_required()
    persona = await db.get(Persona, x_mock_persona_id)
    if persona is None:
        raise _mock_persona_required()
    return persona


async def get_persona_id(persona: Annotated[Persona, Depends(get_persona)]) -> str:
    return persona.id


async def list_personas(db: DbSession) -> list[Persona]:
    result = await db.execute(select(Persona).order_by(Persona.id))
    return list(result.scalars())
