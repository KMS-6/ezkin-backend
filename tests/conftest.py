import os
from collections.abc import AsyncIterator

os.environ.setdefault("AAC_AUTH_SECRET", "test-only-auth-secret")
os.environ.setdefault("AAC_ADMIN_API_KEY", "test-only-admin-key")
os.environ.setdefault("AAC_PARTNER_API_KEY", "test-only-partner-key")

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.persona import Persona

TEST_PERSONA_ID = "persona_001"
ADMIN_HEADERS = {"X-Admin-Key": "test-only-admin-key"}
PARTNER_HEADERS = {"X-Partner-Key": "test-only-partner-key"}


@pytest.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """An AsyncClient wired to a fresh in-memory SQLite DB, seeded with one persona."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            Persona(
                id=TEST_PERSONA_ID,
                label="테스트 페르소나",
                summary_traits={"skin_type": "복합성"},
            )
        )
        await session.commit()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.fixture
def persona_headers() -> dict[str, str]:
    return {"X-Mock-Persona-Id": TEST_PERSONA_ID}
