from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.weather import WeatherSnapshot
from app.modules.briefings import logic as briefings_logic
from app.modules.briefings import router as briefings_router
from tests.conftest import ADMIN_HEADERS, PARTNER_HEADERS, TEST_PERSONA_ID

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
    assert body["routine"][0]["note"] == "보습을 마무리해 주세요."

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


async def test_briefing_night_snack_poor_sleep_and_dry_weather_scenario(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """ "야식 + 부족한 수면 + 건조한 날씨 → very_high, 비타민C 생략, 진정 토너/수분 크림 사용"
    시나리오. 수면·HRV는 Galaxy Watch를 흉내 낸 health-data 웹훅으로, 날씨는 WeatherSnapshot
    시드로, 식습관은 실제 daily-metrics API로 넣어 엔드투엔드로 검증한다.
    """
    today = AFTER_READY_TIME.date().isoformat()

    weather_consent = await client.put(
        "/api/v1/consents/weather_location", headers=persona_headers, json={"consented": True}
    )
    assert weather_consent.status_code == 200
    health_consent = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert health_consent.status_code == 200

    # 건조한 날씨(습도 20%) — 관측 시각은 브리핑 생성 시점(AFTER_READY_TIME) 6시간 이내.
    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=AFTER_READY_TIME - timedelta(hours=1),
            humidity_percent=20.0,
            source="mock",
        )
    )
    # HRV baseline(14일 평균 50ms) 형성 — 오늘 값은 웹훅으로 넣는다.
    for i in range(1, 15):
        db_session.add(
            DailyMetric(
                persona_id=TEST_PERSONA_ID,
                metric_date=AFTER_READY_TIME.date() - timedelta(days=i),
                hrv_ms=50.0,
            )
        )
    await db_session.commit()

    # Galaxy Watch → Health Connect → 앱이 오늘자 수면·HRV를 보냈다고 가정(웹훅 payload).
    health_data = await client.post(
        "/api/v1/integrations/health-data",
        headers={**PARTNER_HEADERS, "Idempotency-Key": "idem-briefing-scenario-health"},
        json={
            "user_token": TEST_PERSONA_ID,
            "metric_date": today,
            "sleep_hours": 4.5,
            "hrv_ms": 35.0,
        },
    )
    assert health_data.status_code == 200

    # 야식 기록(수동 입력).
    diet = await client.post(
        "/api/v1/daily-metrics/manual",
        headers=persona_headers,
        json={
            "metric_date": today,
            "water_intake_level": "under_3_glasses",
            "diet_flag": "late_night_meal",
        },
    )
    assert diet.status_code == 200

    # My Shelf: 비타민C 앰플(주의 성분) + 진정 토너 + 수분 크림.
    ingredient = await client.post(
        "/api/v1/admin/ingredients",
        headers=ADMIN_HEADERS,
        json={"name": "비타민C", "risk_level": "caution", "target_concern": "고위험일 자극"},
    )
    assert ingredient.status_code == 201
    await client.post(
        "/api/v1/cosmetics",
        headers=persona_headers,
        data={
            "brand": "AAC",
            "product_name": "비타민C 앰플",
            "product_type": "serum",
            "ingredients_raw": '["비타민C"]',
        },
    )
    await client.post(
        "/api/v1/cosmetics",
        headers=persona_headers,
        data={
            "brand": "AAC",
            "product_name": "진정 토너",
            "product_type": "toner",
            "ingredients_raw": '["판테놀"]',
        },
    )
    await client.post(
        "/api/v1/cosmetics",
        headers=persona_headers,
        data={
            "brand": "AAC",
            "product_name": "수분 크림",
            "product_type": "moisturizer",
            "ingredients_raw": '["세라마이드"]',
        },
    )

    response = await client.get("/api/v1/briefings/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["risk_level"] == "very_high"

    factor_types = {factor["type"] for factor in body["contributing_factors"]}
    assert factor_types == {"sleep", "hrv", "diet", "weather"}

    routine_names = [step["name"] for step in body["routine"]]
    assert routine_names == ["AAC 진정 토너", "AAC 수분 크림"]
    # very_high(고위험일)이므로 토너·크림 모두 강화된 사용법 안내를 받는다.
    routine_notes = [step["note"] for step in body["routine"]]
    assert routine_notes == [
        "자극을 줄이도록 겹겹이 얇게 발라 주세요.",
        "수분 손실을 막기 위해 평소보다 두껍게 발라 주세요.",
    ]

    skip_names = [item["name"] for item in body["skip"]]
    assert skip_names == ["AAC 비타민C 앰플"]

    assert body["data_coverage"] == {
        "weather": True,
        "watch": True,
        "skin_scan": False,
        "my_shelf": True,
        "baseline_established": True,
    }
    assert "정확도가 제한된 상태" not in body["limitation_notice"]
