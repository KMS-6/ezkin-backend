from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
async def test_client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_submit_camera_scan_returns_202(test_client: AsyncClient) -> None:
    headers = {
        "X-Mock-Persona-Id": "persona_a1_seoyeon",
        "Idempotency-Key": str(uuid4()),
    }
    payload = {
        "capture_method": "camera",
        "image_key": "uploads/camera_01.jpg",
    }
    response = await test_client.post("/api/v1/skin-scans", headers=headers, json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "scan_id" in data
    assert data["status"] == "processing"
    assert data["capture_method"] == "camera"
    assert "Location" in response.headers
    assert response.headers["Retry-After"] == "1"


@pytest.mark.asyncio
async def test_submit_questionnaire_scan_and_get(test_client: AsyncClient) -> None:
    headers = {
        "X-Mock-Persona-Id": "persona_b1_eunji",
        "Idempotency-Key": str(uuid4()),
    }
    payload = {
        "capture_method": "questionnaire",
        "answers": {
            "redness": "mild",
            "tightness": "moderate",
            "oiliness": "none",
            "new_lesions": False,
        },
    }
    post_res = await test_client.post("/api/v1/skin-scans", headers=headers, json=payload)
    assert post_res.status_code == 202
    scan_id = post_res.json()["scan_id"]

    get_res = await test_client.get(
        f"/api/v1/skin-scans/{scan_id}",
        headers={"X-Mock-Persona-Id": "persona_b1_eunji"},
    )
    assert get_res.status_code == 200
    scan_data = get_res.json()
    assert scan_data["id"] == scan_id
    assert scan_data["status"] == "completed"
    assert scan_data["lower_accuracy"] is True
    assert scan_data["scores"]["redness"] == 0.3


@pytest.mark.asyncio
async def test_idempotency_conflict_returns_409(test_client: AsyncClient) -> None:
    key = str(uuid4())
    headers = {
        "X-Mock-Persona-Id": "persona_a1_seoyeon",
        "Idempotency-Key": key,
    }
    res1 = await test_client.post(
        "/api/v1/skin-scans",
        headers=headers,
        json={"capture_method": "camera", "image_key": "uploads/1.jpg"},
    )
    assert res1.status_code == 202

    res2 = await test_client.post(
        "/api/v1/skin-scans",
        headers=headers,
        json={"capture_method": "camera", "image_key": "uploads/2.jpg"},
    )
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_list_scans_pagination_api(test_client: AsyncClient) -> None:
    headers = {"X-Mock-Persona-Id": "persona_c1_minjun"}
    for i in range(5):
        await test_client.post(
            "/api/v1/skin-scans",
            headers={**headers, "Idempotency-Key": f"key-api-{i}"},
            json={"capture_method": "camera", "image_key": f"uploads/{i}.jpg"},
        )

    res1 = await test_client.get("/api/v1/skin-scans?limit=3", headers=headers)
    assert res1.status_code == 200
    page1 = res1.json()
    assert len(page1["items"]) == 3
    assert page1["next_cursor"] is not None

    res2 = await test_client.get(
        f"/api/v1/skin-scans?limit=3&cursor={page1['next_cursor']}",
        headers=headers,
    )
    assert res2.status_code == 200
    page2 = res2.json()
    assert len(page2["items"]) == 2
    assert page2["next_cursor"] is None
