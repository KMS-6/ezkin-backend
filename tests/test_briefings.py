from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.weather import WeatherSnapshot
from app.modules.briefings import logic as briefings_logic
from app.modules.briefings import router as briefings_router
from tests.conftest import TEST_PERSONA_ID

KST = ZoneInfo("Asia/Seoul")
AFTER_READY_TIME = datetime(2026, 8, 16, 9, 0, tzinfo=KST)


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        return AFTER_READY_TIME if tz else AFTER_READY_TIME.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _freeze_briefing_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(briefings_logic, "datetime", _FixedDatetime)
    monkeypatch.setattr(briefings_router, "datetime", _FixedDatetime)


async def test_briefing_generates_and_is_cached(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/v1/cosmetics",
        headers=persona_headers,
        data={"brand": "AAC", "product_name": "보습 크림", "product_type": "moisturizer"},
    )

    first = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "ready"
    assert body["risk_level"] == "low"
    assert body["common_knowledge"] is None
    assert len(body["routine"]) == 1

    second = await client.get("/api/v1/briefings/today", headers=persona_headers)
    # SQLite round-trips DateTime(timezone=True) without an offset suffix, so compare the
    # wall-clock portion only — this proves the briefing was cached, not regenerated.
    assert second.json()["generated_at"][:19] == body["generated_at"][:19]
    assert second.json()["headline"] == body["headline"]


async def test_prescription_reuses_briefing_routine(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/v1/cosmetics",
        headers=persona_headers,
        data={"brand": "AAC", "product_name": "약산성 클렌저", "product_type": "cleanser"},
    )
    await client.get("/api/v1/briefings/today", headers=persona_headers)

    response = await client.get("/api/v1/prescriptions/2026-08-16", headers=persona_headers)
    assert response.status_code == 200
    assert response.json()["steps"][0]["name"] == "AAC 약산성 클렌저"

    future_response = await client.get("/api/v1/prescriptions/2026-08-17", headers=persona_headers)
    assert future_response.status_code == 422

    missing_response = await client.get("/api/v1/prescriptions/2026-08-01", headers=persona_headers)
    assert missing_response.status_code == 404


async def test_notification_settings_upsert(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.patch(
        "/api/v1/notifications/settings",
        headers=persona_headers,
        json={"morning_briefing_enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["morning_briefing_enabled"] is False


async def test_briefing_reflects_consented_weather_in_factors_and_coverage(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/weather_location", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=AFTER_READY_TIME - timedelta(hours=1),
            uv_index=9.0,
            humidity_percent=20.0,
            source="mock",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "moderate"
    assert body["data_coverage"]["weather"] is True
    assert body["data_coverage"]["watch"] is False
    factor_types = {factor["type"] for factor in body["contributing_factors"]}
    assert factor_types == {"weather"}


async def test_briefing_data_coverage_false_without_any_consent(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data_coverage"]["weather"] is False
    assert body["data_coverage"]["watch"] is False
    assert body["data_coverage"]["baseline_established"] is False


async def test_briefing_without_my_shelf_products_includes_registration_notice(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data_coverage"]["my_shelf"] is False
    assert body["routine"] == []
    assert "등록된 화장품이 없어" in body["summary"]


async def test_briefing_hrv_baseline_established_adds_hrv_factor(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    baseline_date = AFTER_READY_TIME.date()
    for i in range(1, 15):
        db_session.add(
            DailyMetric(
                persona_id=TEST_PERSONA_ID,
                metric_date=baseline_date - timedelta(days=i),
                hrv_ms=50.0,
            )
        )
    db_session.add(DailyMetric(persona_id=TEST_PERSONA_ID, metric_date=baseline_date, hrv_ms=35.0))
    await db_session.commit()

    response = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data_coverage"]["baseline_established"] is True
    assert body["data_coverage"]["watch"] is True
    factor_types = {factor["type"] for factor in body["contributing_factors"]}
    assert "hrv" in factor_types
    assert "정확도가 제한된 상태" not in body["limitation_notice"]


async def test_briefing_hrv_baseline_not_established_notes_limited_accuracy(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    # 14일 미만의 HRV 기록만 존재 — baseline 미형성.
    baseline_date = AFTER_READY_TIME.date()
    for i in range(1, 5):
        db_session.add(
            DailyMetric(
                persona_id=TEST_PERSONA_ID,
                metric_date=baseline_date - timedelta(days=i),
                hrv_ms=50.0,
            )
        )
    await db_session.commit()

    response = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data_coverage"]["baseline_established"] is False
    factor_types = {factor["type"] for factor in body["contributing_factors"]}
    assert "hrv" not in factor_types
    assert "정확도가 제한된 상태" in body["limitation_notice"]
