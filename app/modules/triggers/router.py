from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.models.generation import Generation
from app.models.skin_scan import SkinScan
from app.models.sos import SosMessage, SosSession
from app.modules.triggers.logic import build_pattern_analysis, is_urgent, match_faq
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
            detail="insufficient_data_history: 완료된 스캔에서만 패턴 분석을 제공합니다.",
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

    if is_urgent(payload.message):
        reply_type = "safety"
        reply = "앱의 일반 관리 안내 범위를 벗어납니다. 즉시 의료기관에 문의해 주세요."
        safety_flag = "urgent_symptom"
        referral = True
        matched_faq = None
    else:
        faq = match_faq(payload.message)
        if faq is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="규칙 기반 응답을 찾지 못했습니다. LLM 보완 로직은 미연동입니다.",
            )
        reply_type, reply, safety_flag, referral = "answer", faq["reply"], None, False
        matched_faq = {"faq_id": faq["faq_id"], "version": faq["version"]}

    message = SosMessage(
        session_id=session.id,
        persona_id=persona_id,
        message=payload.message,
        reply_type=reply_type,
        reply=reply,
        matched_faq=matched_faq,
        safety_flag=safety_flag,
        expert_referral_suggested=referral,
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
        referenced_cosmetic_ids=message.referenced_cosmetic_ids,
        safety_flag=message.safety_flag,
        expert_referral_suggested=message.expert_referral_suggested,
    )
