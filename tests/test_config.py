import pytest
from pydantic import ValidationError

from app.core.config import Settings, database_engine_options


def test_render_postgres_url_uses_asyncpg_driver() -> None:
    settings = Settings(database_url="postgresql://user:password@host/database")

    assert settings.database_url == "postgresql+asyncpg://user:password@host/database"


def test_explicit_async_driver_is_preserved() -> None:
    url = "postgresql+asyncpg://user:password@host/database"

    assert Settings(database_url=url).database_url == url


def test_cors_origins_accepts_deployed_frontend() -> None:
    origin = "https://wize-web.onrender.com"

    assert Settings(cors_origins=[origin]).cors_origins == [origin]


def test_production_requires_explicit_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AAC_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="AAC_DATABASE_URL"):
        Settings(environment="production")


def test_production_rejects_sqlite_database() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(environment="production", database_url="sqlite+aiosqlite:///./aac.db")


def test_postgres_engine_uses_connection_pool_health_checks() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:password@host/database",
        database_pool_size=7,
        database_max_overflow=3,
        database_pool_timeout=12,
        database_pool_recycle=600,
    )

    assert database_engine_options(settings) == {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": 7,
        "max_overflow": 3,
        "pool_timeout": 12,
        "pool_recycle": 600,
    }


def test_sqlite_engine_does_not_receive_postgres_pool_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AAC_DATABASE_URL", raising=False)
    monkeypatch.delenv("AAC_ENVIRONMENT", raising=False)
    assert database_engine_options(Settings()) == {"echo": False}
