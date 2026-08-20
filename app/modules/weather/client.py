"""기상청 공공데이터포털 API 호출. ADR 003.

키 미설정, 네트워크 오류, 응답 파싱 실패는 모두 여기서 삼키고 None을 반환한다
(임의 날씨 생성 금지, 기존 Anthropic 키 미설정 폴백과 동일한 "선택적 기능
degrade" 원칙). 예외를 상위(risk/briefing 로직)로 전파하지 않는다.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
_UV_URL = "https://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4"

_REQUEST_TIMEOUT_SECONDS = 5.0


@dataclass
class WeatherApiResult:
    temperature_c: float | None
    humidity_percent: float | None
    uv_index: float | None
    weather_condition: str | None


def _base_datetime_for_ncst(now: datetime) -> tuple[str, str]:
    """초단기실황은 매시 40분 이후 관측치가 갱신된다. 40분 이전이면 전 시간 정시로
    조회한다."""
    if now.minute < 40:
        now = now.replace(minute=0) - timedelta(hours=1)
    return now.strftime("%Y%m%d"), now.strftime("%H00")


async def fetch_current_weather(nx: int, ny: int) -> WeatherApiResult | None:
    """온도/습도(초단기실황) + UV지수(생활기상지수)를 조회한다.

    API 키가 없거나 호출/파싱이 실패하면 None을 반환한다.
    """
    if settings.weather_api_key is None:
        return None

    service_key = settings.weather_api_key.get_secret_value()
    now = datetime.now(KST)
    base_date, base_time = _base_datetime_for_ncst(now)

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            ncst_response = await client.get(
                _NCST_URL,
                params={
                    "serviceKey": service_key,
                    "dataType": "JSON",
                    "base_date": base_date,
                    "base_time": base_time,
                    "nx": nx,
                    "ny": ny,
                    "numOfRows": 100,
                },
            )
            ncst_response.raise_for_status()
            temperature_c, humidity_percent = _parse_ncst(ncst_response.json())

            uv_response = await client.get(
                _UV_URL,
                params={
                    "serviceKey": service_key,
                    "dataType": "JSON",
                    "areaNo": f"{nx}{ny}",
                    "time": now.strftime("%Y%m%d%H"),
                },
            )
            uv_response.raise_for_status()
            uv_index = _parse_uv(uv_response.json())
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("기상청 API 호출/파싱 실패: nx=%s ny=%s error=%s", nx, ny, exc)
        return None

    return WeatherApiResult(
        temperature_c=temperature_c,
        humidity_percent=humidity_percent,
        uv_index=uv_index,
        weather_condition=None,
    )


def _parse_ncst(payload: dict) -> tuple[float | None, float | None]:
    items = payload["response"]["body"]["items"]["item"]
    temperature_c: float | None = None
    humidity_percent: float | None = None
    for item in items:
        if item["category"] == "T1H":
            temperature_c = float(item["obsrValue"])
        elif item["category"] == "REH":
            humidity_percent = float(item["obsrValue"])
    return temperature_c, humidity_percent


def _parse_uv(payload: dict) -> float | None:
    items = payload["response"]["body"]["items"]["item"]
    if not items:
        return None
    # 가장 가까운 예보 시각(첫 항목)의 UV지수를 사용한다.
    first = items[0]
    value = first.get("h0") or first.get("today")
    return float(value) if value is not None else None
