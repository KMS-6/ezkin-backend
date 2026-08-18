import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.admin_auth import get_admin

_app = FastAPI()


@_app.get("/admin-only")
async def admin_only(_: None = Depends(get_admin)) -> dict[str, str]:
    return {"ok": "true"}


@pytest.mark.asyncio
async def test_admin_key_missing_returns_403() -> None:
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        resp = await c.get("/admin-only")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_key_wrong_returns_403() -> None:
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        resp = await c.get("/admin-only", headers={"X-Admin-Key": "wrong-key"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_key_correct_returns_200() -> None:
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        resp = await c.get("/admin-only", headers={"X-Admin-Key": "test-only-admin-key"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": "true"}
