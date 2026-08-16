from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.modules.briefings import logic as briefings_logic
from app.modules.briefings import router as briefings_router

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
