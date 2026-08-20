"""날씨 조회 서비스 — TTL 캐시, 위치 조회, API 실패 폴백 검증. ADR 003."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.onboarding import OnboardingProfile
from app.models.weather import WeatherSnapshot
from app.modules.weather import service as weather_service
from app.modules.weather.client import WeatherApiResult
from app.modules.weather.grid import SEOUL_LATITUDE, SEOUL_LONGITUDE, latlon_to_grid
from tests.conftest import TEST_PERSONA_ID


async def test_uses_cached_snapshot_within_ttl(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=now - timedelta(minutes=10),
            uv_index=5.0,
            humidity_percent=40.0,
            source="kma_api",
        )
    )
    await db_session.commit()

    async def _should_not_be_called(nx: int, ny: int):
        raise AssertionError("TTL 이내에는 API를 다시 호출하면 안 된다")

    monkeypatch.setattr(weather_service, "fetch_current_weather", _should_not_be_called)

    result = await weather_service.get_or_fetch_weather(db_session, TEST_PERSONA_ID, now)

    assert result is not None
    assert result.uv_index == 5.0


async def test_refetches_after_ttl_expires(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=now - timedelta(minutes=settings.weather_cache_ttl_minutes + 5),
            uv_index=5.0,
            humidity_percent=40.0,
            source="kma_api",
        )
    )
    await db_session.commit()

    called_with = {}

    async def _fake_fetch(nx: int, ny: int):
        called_with["nx"] = nx
        called_with["ny"] = ny
        return WeatherApiResult(
            temperature_c=18.0, humidity_percent=60.0, uv_index=8.0, weather_condition=None
        )

    monkeypatch.setattr(weather_service, "fetch_current_weather", _fake_fetch)

    result = await weather_service.get_or_fetch_weather(db_session, TEST_PERSONA_ID, now)

    assert result is not None
    assert result.uv_index == 8.0
    assert result.source == "kma_api"
    # 위도/경도 미저장 persona → 서울 기본 좌표로 폴백
    assert (called_with["nx"], called_with["ny"]) == latlon_to_grid(SEOUL_LATITUDE, SEOUL_LONGITUDE)


async def test_uses_persona_location_when_available(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        OnboardingProfile(persona_id=TEST_PERSONA_ID, latitude=35.1796, longitude=129.0756)
    )
    await db_session.commit()

    called_with = {}

    async def _fake_fetch(nx: int, ny: int):
        called_with["nx"] = nx
        called_with["ny"] = ny
        return WeatherApiResult(
            temperature_c=20.0, humidity_percent=50.0, uv_index=6.0, weather_condition=None
        )

    monkeypatch.setattr(weather_service, "fetch_current_weather", _fake_fetch)

    await weather_service.get_or_fetch_weather(db_session, TEST_PERSONA_ID, now)

    assert (called_with["nx"], called_with["ny"]) == latlon_to_grid(35.1796, 129.0756)


async def test_falls_back_to_stale_cache_when_api_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=now - timedelta(minutes=settings.weather_cache_ttl_minutes + 5),
            uv_index=3.0,
            humidity_percent=45.0,
            source="kma_api",
        )
    )
    await db_session.commit()

    async def _fake_fetch(nx: int, ny: int):
        return None

    monkeypatch.setattr(weather_service, "fetch_current_weather", _fake_fetch)

    result = await weather_service.get_or_fetch_weather(db_session, TEST_PERSONA_ID, now)

    assert result is not None
    assert result.uv_index == 3.0


async def test_returns_none_when_no_cache_and_api_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)

    async def _fake_fetch(nx: int, ny: int):
        return None

    monkeypatch.setattr(weather_service, "fetch_current_weather", _fake_fetch)

    result = await weather_service.get_or_fetch_weather(db_session, TEST_PERSONA_ID, now)

    assert result is None
