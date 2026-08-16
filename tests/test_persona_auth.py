import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture()
async def client(db_session: AsyncSession):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_missing_header_returns_400(client):
    response = await client.get("/api/v1/analysis/eligibility")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "mock_persona_required"


async def test_invalid_persona_returns_400(client):
    response = await client.get(
        "/api/v1/analysis/eligibility",
        headers={"X-Mock-Persona-Id": "invalid_persona"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "mock_persona_required"


async def test_valid_persona_passes(client):
    response = await client.get(
        "/api/v1/analysis/eligibility",
        headers={"X-Mock-Persona-Id": "persona_a1_seoyeon"},
    )
    # 인증은 통과해야 함 (400이 아닌 다른 응답)
    assert response.status_code != 400
