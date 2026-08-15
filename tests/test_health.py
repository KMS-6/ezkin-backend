from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class ReadySession:
    async def execute(self, statement: object) -> None:
        assert str(statement) == "SELECT 1"


class UnavailableSession:
    async def execute(self, statement: object) -> None:
        raise ConnectionError("database unavailable")


def test_database_readiness() -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield ReadySession()  # type: ignore[misc]

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_readiness_reports_unavailable_database() -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield UnavailableSession()  # type: ignore[misc]

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
