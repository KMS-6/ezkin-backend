"""날씨 조회 서비스 — TTL 캐시 + persona 위치 조회. ADR 003.

risk/briefing 로직은 이 모듈의 `get_or_fetch_weather`만 호출한다. API 키 미설정,
호출 실패, 위치 정보 없음 등 모든 예외 상황에서 예외를 던지지 않고 캐시된 값 또는
None을 반환해 기존 "임의 날씨 생성 금지" 동작을 유지한다.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.onboarding import OnboardingProfile
from app.models.weather import WeatherSnapshot
from app.modules.weather.client import fetch_current_weather
from app.modules.weather.grid import (
    SEOUL_LATITUDE,
    SEOUL_LONGITUDE,
    latlon_to_grid,
    nearest_sido_area_code,
)

WEATHER_SOURCE_API = "kma_api"


def _as_naive_utc(value: datetime) -> datetime:
    """SQLite는 DateTime(timezone=True)를 offset 없이 round-trip한다 — 비교 전에
    naive UTC로 정규화한다(risk/logic.py의 동일 헬퍼와 같은 이유)."""
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


async def _load_latest_snapshot(db: AsyncSession, persona_id: str) -> WeatherSnapshot | None:
    result = await db.execute(
        select(WeatherSnapshot)
        .where(WeatherSnapshot.persona_id == persona_id)
        .order_by(WeatherSnapshot.observed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_location(db: AsyncSession, persona_id: str) -> tuple[float, float]:
    profile = await db.get(OnboardingProfile, persona_id)
    if profile is not None and profile.latitude is not None and profile.longitude is not None:
        return profile.latitude, profile.longitude
    return SEOUL_LATITUDE, SEOUL_LONGITUDE


async def get_or_fetch_weather(
    db: AsyncSession, persona_id: str, now: datetime
) -> WeatherSnapshot | None:
    """캐시된 최신 WeatherSnapshot이 TTL 이내면 그대로 반환하고, 아니면 기상청 API를
    호출해 새 스냅샷을 저장한다. API 호출이 실패하면 기존 최신 스냅샷(있다면) 또는
    None을 반환한다.

    `now`는 호출자가 넘긴다 — risk/logic.py의 다른 시계 의존 함수와 동일하게
    Briefing 테스트의 시계 freeze가 적용되도록 하기 위함이다.
    """
    latest = await _load_latest_snapshot(db, persona_id)
    ttl = timedelta(minutes=settings.weather_cache_ttl_minutes)
    if latest is not None and (_as_naive_utc(now) - _as_naive_utc(latest.observed_at)) < ttl:
        return latest

    lat, lon = await _resolve_location(db, persona_id)
    nx, ny = latlon_to_grid(lat, lon)
    area_code = nearest_sido_area_code(lat, lon)
    result = await fetch_current_weather(nx, ny, area_code)
    if result is None:
        return latest

    snapshot = WeatherSnapshot(
        persona_id=persona_id,
        observed_at=now,
        temperature_c=result.temperature_c,
        humidity_percent=result.humidity_percent,
        uv_index=result.uv_index,
        weather_condition=result.weather_condition,
        source=WEATHER_SOURCE_API,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
