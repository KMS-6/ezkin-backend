from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import bearer_scheme, try_decode_access_token
from app.db.session import get_db
from app.models.persona import Persona

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _persona_auth_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "mock_persona_required: 유효한 실사용자 인증 토큰 또는 "
            "X-Mock-Persona-Id 헤더가 필요합니다."
        ),
    )


async def _get_or_create_user_persona(db: AsyncSession, user_id: UUID) -> Persona:
    """실사용자는 str(User.id)를 persona_id로 그대로 사용해, 기존 persona_id 기반 도메인
    테이블/서비스 로직을 변경하지 않고 재사용한다. 최초 호출 시 Persona row를 지연 생성한다."""
    persona_id = str(user_id)
    persona = await db.get(Persona, persona_id)
    if persona is None:
        persona = Persona(id=persona_id, label="일반 사용자", summary_traits={})
        db.add(persona)
        await db.flush()
    return persona


async def get_persona(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    x_mock_persona_id: Annotated[str | None, Header()] = None,
) -> Persona:
    user_id = try_decode_access_token(credentials)
    if user_id is not None:
        return await _get_or_create_user_persona(db, user_id)

    if not x_mock_persona_id:
        raise _persona_auth_required()
    persona = await db.get(Persona, x_mock_persona_id)
    if persona is None:
        raise _persona_auth_required()
    return persona


async def get_persona_id(persona: Annotated[Persona, Depends(get_persona)]) -> str:
    return persona.id


async def list_personas(db: DbSession) -> list[Persona]:
    result = await db.execute(select(Persona).order_by(Persona.id))
    return list(result.scalars())
