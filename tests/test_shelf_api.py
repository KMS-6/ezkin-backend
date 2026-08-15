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
            access_token = user_response.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {access_token}"}

            other_user_response = await client.post(
                "/api/v1/users",
                json={"email": "other@example.com", "nickname": "다른 사용자"},
            )
            other_token = other_user_response.json()["access_token"]

            product_response = await client.post(
                "/api/v1/shelf/products",
                headers=auth_headers,
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
                headers=auth_headers,
            )
            assert list_response.status_code == 200
            assert [item["id"] for item in list_response.json()["items"]] == [product_id]

            unauthenticated_response = await client.get("/api/v1/shelf/products")
            assert unauthenticated_response.status_code == 401

            tampered_response = await client.get(
                "/api/v1/shelf/products",
                headers={"Authorization": f"Bearer {access_token[:-1]}x"},
            )
            assert tampered_response.status_code == 401

            other_user_response = await client.get(
                f"/api/v1/shelf/products/{product_id}",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert other_user_response.status_code == 404

            delete_response = await client.delete(
                f"/api/v1/shelf/products/{product_id}",
                headers=auth_headers,
            )
            assert delete_response.status_code == 204

            empty_response = await client.get(
                "/api/v1/shelf/products",
                headers=auth_headers,
            )
            assert empty_response.json() == {"items": []}
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
