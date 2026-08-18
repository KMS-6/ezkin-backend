from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.models.feedback import GenerationFeedback
from app.models.generation import Generation
from app.modules.feedback.schemas import FeedbackIn, FeedbackOut

router = APIRouter(tags=["feedback"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]


@router.post(
    "/generations/{generation_id}/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    generation_id: str, payload: FeedbackIn, db: DbSession, persona_id: PersonaId
) -> FeedbackOut:
    generation = await db.get(Generation, generation_id)
    if generation is None or generation.persona_id != persona_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="대상을 찾을 수 없습니다."
        )

    feedback = GenerationFeedback(
        generation_id=generation_id,
        persona_id=persona_id,
        rating=payload.rating,
        reason_code=payload.reason_code,
        comment=payload.comment,
    )
    db.add(feedback)
    await db.commit()
    return FeedbackOut(
        id=str(feedback.id),
        generation_id=generation_id,
        rating=feedback.rating,
        reason_code=feedback.reason_code,
        comment=feedback.comment,
    )
