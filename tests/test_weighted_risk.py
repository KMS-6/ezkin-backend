"""기능명세서_briefing.md 6.1/6.2절 가중치 위험도 계산 — /risk-assessments/today 검증.

날씨·HRV baseline은 API로 주입할 방법이 없어(외부 연동 미구현, 4.1/6.3절) `db_session`으로
직접 시드한다.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.weather import WeatherSnapshot
from tests.conftest import TEST_PERSONA_ID

KST = ZoneInfo("Asia/Seoul")


async def test_weather_is_ignored_without_consent(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=datetime.now(UTC),
            uv_index=9.0,
            humidity_percent=20.0,
            source="mock",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "low"
    assert body["contributing_factors"] == []


async def test_uv_and_humidity_raise_risk_with_consent(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/weather_location", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=datetime.now(UTC),
            uv_index=9.0,
            humidity_percent=20.0,
            source="mock",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "moderate"
    factor_text = " ".join(body["contributing_factors"])
    assert "자외선" in factor_text
    assert "습도" in factor_text


async def test_stale_weather_is_excluded(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/weather_location", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=datetime.now(UTC) - timedelta(hours=12),
            uv_index=9.0,
            humidity_percent=20.0,
            source="mock",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    assert response.json()["contributing_factors"] == []


async def test_single_factor_alone_does_not_reach_high_risk(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """6.2절: 개별 조건 하나만으로 high·very_high를 확정하지 않는다."""
    consent = await client.put(
        "/api/v1/consents/weather_location", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=datetime.now(UTC),
            uv_index=9.0,
            source="mock",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    assert response.json()["risk_level"] not in ("high", "very_high")


async def test_hrv_baseline_not_established_with_insufficient_history(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    today = datetime.now(KST).date()
    for i in range(1, 5):
        db_session.add(
            DailyMetric(
                persona_id=TEST_PERSONA_ID, metric_date=today - timedelta(days=i), hrv_ms=50.0
            )
        )
    await db_session.commit()

    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "low"
    assert body["contributing_factors"] == []


async def test_hrv_drop_from_established_baseline_raises_risk(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert consent.status_code == 200

    today = datetime.now(KST).date()
    for i in range(1, 15):
        db_session.add(
            DailyMetric(
                persona_id=TEST_PERSONA_ID, metric_date=today - timedelta(days=i), hrv_ms=50.0
            )
        )
    db_session.add(DailyMetric(persona_id=TEST_PERSONA_ID, metric_date=today, hrv_ms=35.0))
    await db_session.commit()

    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "moderate"
    assert any("HRV" in factor for factor in body["contributing_factors"])
