from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.idempotency import check_idempotency, store_idempotency
from app.core.mock_persona import get_persona_id
from app.core.partner_auth import require_partner_key
from app.db.session import get_db
from app.models.metrics import DailyMetric
from app.models.onboarding import Consent
from app.models.persona import Persona
from app.modules.health_metrics.schemas import (
    DailyMetricIn,
    DailyMetricOut,
    HealthDataIn,
    HealthDataReceived,
)

router = APIRouter(tags=["metrics"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]


@router.post(
    "/integrations/health-data",
    response_model=HealthDataReceived,
    dependencies=[Depends(require_partner_key)],
)
async def receive_health_data(
    payload: HealthDataIn,
    db: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> HealthDataReceived:
    persona = await db.get(Persona, payload.user_token)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="등록되지 않은 user_token입니다.",
        )

    idempotency_payload = payload.model_dump(mode="json")
    cached = await check_idempotency(
        db,
        scope="health-data",
        subject=payload.user_token,
        key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return HealthDataReceived(**cached)

    consent_result = await db.execute(
        select(Consent).where(Consent.persona_id == persona.id, Consent.type == "apple_health")
    )
    consent = consent_result.scalar_one_or_none()
    health_consented = consent is not None and consent.consented
    if health_consented:
        result = await db.execute(
            select(DailyMetric).where(
                DailyMetric.persona_id == persona.id,
                DailyMetric.metric_date == payload.metric_date,
            )
        )
        metric = result.scalar_one_or_none()
        if metric is None:
            metric = DailyMetric(persona_id=persona.id, metric_date=payload.metric_date)
            db.add(metric)
        metric.sleep_hours = payload.sleep_hours
        metric.hrv_ms = payload.hrv_ms
        metric.active_energy_kcal = payload.active_energy_kcal
        await db.flush()

    response = HealthDataReceived()
    cached = await store_idempotency(
        db,
        scope="health-data",
        subject=payload.user_token,
        key=idempotency_key,
        payload=idempotency_payload,
        response_status=status.HTTP_200_OK,
        response_body=response.model_dump(),
    )
    if cached is not None:
        return HealthDataReceived(**cached)
    await db.commit()
    return response


@router.post("/daily-metrics/manual", response_model=DailyMetricOut)
async def upsert_daily_metric(
    payload: DailyMetricIn, db: DbSession, persona_id: PersonaId
) -> DailyMetricOut:
    result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == persona_id, DailyMetric.metric_date == payload.metric_date
        )
    )
    metric = result.scalar_one_or_none()
    if metric is None:
        metric = DailyMetric(persona_id=persona_id, metric_date=payload.metric_date)
        db.add(metric)
    metric.hydration_level = payload.hydration_level
    metric.diet_flag = payload.diet_flag
    await db.commit()
    await db.refresh(metric)
    return DailyMetricOut(
        metric_date=metric.metric_date,
        hydration_level=metric.hydration_level,
        diet_flag=metric.diet_flag,
        updated_at=metric.updated_at,
    )
