from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.scan import SkinScan


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
    assert data["status"] == "failed"
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
    post_data = post_res.json()
    assert post_data["status"] == "completed"
    scan_id = post_data["scan_id"]

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


@pytest.mark.asyncio
async def test_list_scans_limit_validation(test_client: AsyncClient) -> None:
    headers = {"X-Mock-Persona-Id": "persona_c1_minjun"}
    # limit < 1
    res_zero = await test_client.get("/api/v1/skin-scans?limit=0", headers=headers)
    assert res_zero.status_code == 422

    # limit > 100
    res_over = await test_client.get("/api/v1/skin-scans?limit=101", headers=headers)
    assert res_over.status_code == 422

    # limit within bounds
    res_valid = await test_client.get("/api/v1/skin-scans?limit=50", headers=headers)
    assert res_valid.status_code == 200


@pytest.mark.asyncio
async def test_list_scans_pagination_tie_break_by_id(test_client: AsyncClient) -> None:
    headers = {"X-Mock-Persona-Id": "persona_a2_haneul"}
    fixed_time = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)

    get_db_override = app.dependency_overrides[get_db]
    async for db in get_db_override():
        scans = [
            SkinScan(
                persona_id="persona_a2_haneul",
                capture_method="camera",
                image_key=f"uploads/tie_{i}.jpg",
                status="failed",
                created_at=fixed_time,
                idempotency_key=f"key-tie-{i}",
                idempotency_payload_hash=f"hash-{i}",
            )
            for i in range(4)
        ]
        db.add_all(scans)
        await db.commit()
        expected_ids = [str(s.id) for s in sorted(scans, key=lambda s: s.id, reverse=True)]
        break

    res1 = await test_client.get("/api/v1/skin-scans?limit=2", headers=headers)
    assert res1.status_code == 200
    page1 = res1.json()
    assert len(page1["items"]) == 2
    assert [item["id"] for item in page1["items"]] == expected_ids[:2]
    assert page1["next_cursor"] is not None

    res2 = await test_client.get(
        f"/api/v1/skin-scans?limit=2&cursor={page1['next_cursor']}",
        headers=headers,
    )
    assert res2.status_code == 200
    page2 = res2.json()
    assert len(page2["items"]) == 2
    assert [item["id"] for item in page2["items"]] == expected_ids[2:]
    assert page2["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_scans_cursor_other_persona_ignored(test_client: AsyncClient) -> None:
    # Persona A의 스캔 생성
    headers_a = {"X-Mock-Persona-Id": "persona_a1_seoyeon"}
    res_a = await test_client.post(
        "/api/v1/skin-scans",
        headers={**headers_a, "Idempotency-Key": "key-cursor-a"},
        json={"capture_method": "camera", "image_key": "uploads/a.jpg"},
    )
    assert res_a.status_code == 202
    scan_id_a = res_a.json()["scan_id"]

    # Persona B의 스캔 생성
    headers_b = {"X-Mock-Persona-Id": "persona_b2_doyoon"}
    res_b = await test_client.post(
        "/api/v1/skin-scans",
        headers={**headers_b, "Idempotency-Key": "key-cursor-b"},
        json={"capture_method": "camera", "image_key": "uploads/b.jpg"},
    )
    assert res_b.status_code == 202

    # Persona A의 scan_id를 커서로 만들어 Persona B가 조회 시도
    import base64

    fake_cursor = base64.urlsafe_b64encode(scan_id_a.encode()).decode().rstrip("=")
    res_list = await test_client.get(
        f"/api/v1/skin-scans?cursor={fake_cursor}",
        headers=headers_b,
    )
    assert res_list.status_code == 200
    # 타 페르소나의 커서는 무시되어 Persona B의 목록이 정상 반환됨
    items = res_list.json()["items"]
    assert len(items) == 1
    assert items[0]["persona_id"] == "persona_b2_doyoon"
