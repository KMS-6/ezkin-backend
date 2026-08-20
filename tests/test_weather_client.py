"""기상청 API 클라이언트 — 실제 네트워크 호출 없이 httpx.MockTransport로 검증한다.

키 미설정/네트워크 오류/파싱 실패가 모두 예외 없이 None을 반환하는지 확인한다
(ADR 003: 임의 날씨 생성 금지, 조용한 폴백 원칙).
"""

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.modules.weather import client as weather_client

NCST_BODY = {
    "response": {
        "body": {
            "items": {
                "item": [
                    {"category": "T1H", "obsrValue": "21.5"},
                    {"category": "REH", "obsrValue": "55"},
                ]
            }
        }
    }
}
UV_BODY = {"response": {"body": {"items": {"item": [{"h0": "7"}]}}}}


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    original_client = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(weather_client.httpx, "AsyncClient", _client_factory)


async def test_returns_none_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "weather_api_key", None)

    result = await weather_client.fetch_current_weather(60, 127, "1100000000")

    assert result is None


async def test_returns_parsed_weather_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "weather_api_key", SecretStr("test-key"))

    def handler(request: httpx.Request) -> httpx.Response:
        if "getUltraSrtNcst" in str(request.url):
            return httpx.Response(200, json=NCST_BODY)
        return httpx.Response(200, json=UV_BODY)

    _install_transport(monkeypatch, handler)

    result = await weather_client.fetch_current_weather(60, 127, "1100000000")

    assert result is not None
    assert result.temperature_c == 21.5
    assert result.humidity_percent == 55.0
    assert result.uv_index == 7.0


async def test_returns_none_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "weather_api_key", SecretStr("test-key"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _install_transport(monkeypatch, handler)

    result = await weather_client.fetch_current_weather(60, 127, "1100000000")

    assert result is None


async def test_returns_none_on_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "weather_api_key", SecretStr("test-key"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    _install_transport(monkeypatch, handler)

    result = await weather_client.fetch_current_weather(60, 127, "1100000000")

    assert result is None
