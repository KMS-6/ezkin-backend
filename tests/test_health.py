from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.metrics import DailyMetric
from app.models.onboarding import Consent
from tests.conftest import PARTNER_HEADERS, TEST_PERSONA_ID


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_data_persisted_when_apple_health_consented(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    response = await client.post(
        "/api/v1/integrations/health-data",
        headers={**PARTNER_HEADERS, "Idempotency-Key": "idem-health-consented"},
        json={
            "user_token": TEST_PERSONA_ID,
            "metric_date": "2026-08-16",
            "sleep_hours": 6.5,
            "hrv_ms": 42.0,
            "active_energy_kcal": 300.0,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"received": True}

    result = await db_session.execute(
        select(DailyMetric).where(DailyMetric.persona_id == TEST_PERSONA_ID)
    )
    metric = result.scalar_one()
    assert metric.sleep_hours == 6.5
    assert metric.hrv_ms == 42.0
    assert metric.active_energy_kcal == 300.0


async def test_health_data_discarded_without_apple_health_consent(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/integrations/health-data",
        headers={**PARTNER_HEADERS, "Idempotency-Key": "idem-health-no-consent"},
        json={
            "user_token": TEST_PERSONA_ID,
            "metric_date": "2026-08-16",
            "sleep_hours": 6.5,
            "hrv_ms": 42.0,
            "active_energy_kcal": 300.0,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"received": True}

    result = await db_session.execute(
        select(DailyMetric).where(DailyMetric.persona_id == TEST_PERSONA_ID)
    )
    assert result.scalar_one_or_none() is None


async def test_health_data_discarded_when_apple_health_consent_explicitly_false(
    client: AsyncClient,
    persona_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200
    revoke = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": False}
    )
    assert revoke.status_code == 200

    result = await db_session.execute(
        select(Consent).where(
            Consent.persona_id == TEST_PERSONA_ID, Consent.type == "apple_health"
        )
    )
    assert result.scalar_one().consented is False

    response = await client.post(
        "/api/v1/integrations/health-data",
        headers={**PARTNER_HEADERS, "Idempotency-Key": "idem-health-revoked-consent"},
        json={
            "user_token": TEST_PERSONA_ID,
            "metric_date": "2026-08-16",
            "sleep_hours": 6.5,
            "hrv_ms": 42.0,
            "active_energy_kcal": 300.0,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"received": True}

    metric_result = await db_session.execute(
        select(DailyMetric).where(DailyMetric.persona_id == TEST_PERSONA_ID)
    )
    assert metric_result.scalar_one_or_none() is None
