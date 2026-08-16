import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("AAC_AUTH_SECRET", "test-only-auth-secret")

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

_TEST_DB_URL = os.environ.get("AAC_DATABASE_URL", "postgresql+asyncpg://aac:aac@localhost:5432/aac")


@pytest.fixture
async def pg_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(pg_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(pg_engine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def _get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
