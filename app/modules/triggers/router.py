from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.models.generation import Generation
from app.models.skin_scan import SkinScan
from app.models.sos import SosMessage, SosSession
from app.modules.triggers.logic import build_chat_reply, build_pattern_analysis
from app.modules.triggers.schemas import (
    PatternAnalysisOut,
    SosMessageIn,
    SosMessageOut,
    SosSessionOut,
)

router = APIRouter(tags=["triggers"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]

QUICK_REPLIES = ["일식을 먹었어요", "트러블이 돋아요", "제품이 안 맞는 것 같아요"]


@router.get("/pattern-analysis", response_model=PatternAnalysisOut)
async def get_pattern_analysis(
    db: DbSession, persona_id: PersonaId, scan_id: Annotated[UUID, Query()]
) -> PatternAnalysisOut:
    scan = await db.get(SkinScan, scan_id)
    if scan is None or scan.persona_id != persona_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="스캔을 찾을 수 없습니다."
        )
    if scan.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="scan_not_completed: 완료된 스캔에서만 패턴 분석을 제공합니다.",
        )
    content = await build_pattern_analysis(db, scan)
    return PatternAnalysisOut(scan_id=str(scan.id), **content)


@router.post("/sos/sessions", response_model=SosSessionOut, status_code=status.HTTP_201_CREATED)
async def create_sos_session(db: DbSession, persona_id: PersonaId) -> SosSessionOut:
    session = SosSession(persona_id=persona_id)
    db.add(session)
    await db.commit()
    return SosSessionOut(session_id=str(session.id), quick_replies=QUICK_REPLIES)


@router.post("/sos/sessions/{session_id}/messages", response_model=SosMessageOut)
async def send_sos_message(
    session_id: UUID, payload: SosMessageIn, db: DbSession, persona_id: PersonaId
) -> SosMessageOut:
    session = await db.get(SosSession, session_id)
    if session is None or session.persona_id != persona_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다."
        )

    result = await build_chat_reply(db, persona_id, payload.message)

    message = SosMessage(
        session_id=session.id,
        persona_id=persona_id,
        message=payload.message,
        reply_type=result["reply_type"],
        reply=result["reply"],
        matched_faq=result["matched_faq"],
        decision=result["decision"],
        referenced_cosmetic_ids=result["referenced_cosmetic_ids"],
        used_contexts=result["used_contexts"],
        safety_flag=result["safety_flag"],
        expert_referral_suggested=result["expert_referral_suggested"],
        intent=result["intent"],
        parse_confidence=result["parse_confidence"],
        llm_escalated=result["llm_escalated"],
    )
    db.add(message)
    await db.flush()
    db.add(Generation(id=str(message.id), persona_id=persona_id, kind="sos_message"))
    await db.commit()

    return SosMessageOut(
        message_id=str(message.id),
        reply_type=message.reply_type,
        reply=message.reply,
        matched_faq=message.matched_faq,
        decision=message.decision,
        referenced_cosmetic_ids=message.referenced_cosmetic_ids,
        used_contexts=message.used_contexts,
        safety_flag=message.safety_flag,
        expert_referral_suggested=message.expert_referral_suggested,
    )
