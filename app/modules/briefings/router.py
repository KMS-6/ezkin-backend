from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.models.briefing import Briefing, NotificationSettings
from app.modules.briefings.logic import BRIEFING_READY_TIME, KST, get_or_generate_briefing
from app.modules.briefings.schemas import (
    NotificationSettingsIn,
    NotificationSettingsOut,
    PrescriptionOut,
    RoutineStep,
)

router = APIRouter(tags=["briefings"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]


@router.get("/briefings/today")
async def get_today_briefing(db: DbSession, persona_id: PersonaId) -> dict:
    briefing = await get_or_generate_briefing(db, persona_id)
    if briefing is not None:
        return {
            "status": "ready",
            "date": briefing.briefing_date.isoformat(),
            "risk_level": briefing.risk_level,
            "headline": briefing.headline,
            "summary": briefing.summary,
            "contributing_factors": briefing.contributing_factors,
            "routine": briefing.routine,
            "skip": briefing.skip,
            "common_knowledge": briefing.common_knowledge,
            "data_coverage": briefing.data_coverage,
            "limitation_notice": briefing.limitation_notice,
            "generated_at": briefing.generated_at.isoformat(),
            "sent_at": briefing.sent_at.isoformat() if briefing.sent_at else None,
        }

    today = datetime.now(KST).date()
    previous_result = await db.execute(
        select(Briefing)
        .where(Briefing.persona_id == persona_id, Briefing.briefing_date < today)
        .order_by(Briefing.briefing_date.desc())
        .limit(1)
    )
    previous = previous_result.scalar_one_or_none()
    return {
        "status": "pending",
        "date": today.isoformat(),
        "generation_expected_at": datetime.combine(
            today, BRIEFING_READY_TIME, tzinfo=KST
        ).isoformat(),
        "previous_briefing": (
            {
                "date": previous.briefing_date.isoformat(),
                "risk_level": previous.risk_level,
                "headline": previous.headline,
            }
            if previous is not None
            else None
        ),
    }


@router.get("/prescriptions/{target_date}", response_model=PrescriptionOut)
async def get_prescription(
    target_date: date, db: DbSession, persona_id: PersonaId
) -> PrescriptionOut:
    today = datetime.now(KST).date()
    if target_date > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="미래 날짜는 조회할 수 없습니다.",
        )

    if target_date == today:
        briefing = await get_or_generate_briefing(db, persona_id)
    else:
        result = await db.execute(
            select(Briefing).where(
                Briefing.persona_id == persona_id, Briefing.briefing_date == target_date
            )
        )
        briefing = result.scalar_one_or_none()

    if briefing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 날짜의 처방 정보를 찾을 수 없습니다.",
        )

    return PrescriptionOut(
        date=target_date,
        steps=[RoutineStep(**step) for step in briefing.routine],
        avoid=[item["reason"] for item in briefing.skip],
        disclaimer="일반적 관리 안내이며 치료·처방 목적이 아닙니다.",
    )


@router.patch("/notifications/settings", response_model=NotificationSettingsOut)
async def update_notification_settings(
    payload: NotificationSettingsIn, db: DbSession, persona_id: PersonaId
) -> NotificationSettingsOut:
    settings_row = await db.get(NotificationSettings, persona_id)
    if settings_row is None:
        settings_row = NotificationSettings(persona_id=persona_id)
        db.add(settings_row)
    settings_row.morning_briefing_enabled = payload.morning_briefing_enabled
    await db.commit()
    await db.refresh(settings_row)
    return NotificationSettingsOut(
        morning_briefing_enabled=settings_row.morning_briefing_enabled,
        updated_at=settings_row.updated_at,
    )
