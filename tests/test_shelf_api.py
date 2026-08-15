from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.mark.asyncio
async def test_user_can_manage_own_shelf_product() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            user_response = await client.post(
                "/api/v1/users",
                json={"email": "shelf@example.com", "nickname": "테스터"},
            )
            assert user_response.status_code == 201
            user_id = user_response.json()["id"]

            product_response = await client.post(
                "/api/v1/shelf/products",
                headers={"X-User-Id": user_id},
                json={
                    "brand": "AAC",
                    "product_name": "보습 크림",
                    "product_type": "moisturizer",
                },
            )
            assert product_response.status_code == 201
            product_id = product_response.json()["id"]
            assert product_response.json()["user_verified_at"] is not None

            list_response = await client.get(
                "/api/v1/shelf/products",
                headers={"X-User-Id": user_id},
            )
            assert list_response.status_code == 200
            assert [item["id"] for item in list_response.json()["items"]] == [product_id]

            delete_response = await client.delete(
                f"/api/v1/shelf/products/{product_id}",
                headers={"X-User-Id": user_id},
            )
            assert delete_response.status_code == 204

            empty_response = await client.get(
                "/api/v1/shelf/products",
                headers={"X-User-Id": user_id},
            )
            assert empty_response.json() == {"items": []}
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
