from app.core.config import Settings


def test_render_postgres_url_uses_asyncpg_driver() -> None:
    settings = Settings(database_url="postgresql://user:password@host/database")

    assert settings.database_url == "postgresql+asyncpg://user:password@host/database"


def test_explicit_async_driver_is_preserved() -> None:
    url = "postgresql+asyncpg://user:password@host/database"

    assert Settings(database_url=url).database_url == url


def test_cors_origins_accepts_deployed_frontend() -> None:
    origin = "https://wize-web.onrender.com"

    assert Settings(cors_origins=[origin]).cors_origins == [origin]


def test_production_requires_non_empty_admin_api_key(monkeypatch) -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AAC_ADMIN_API_KEY"):
        Settings(app_env="production", **{"admin" + "_api_key": ""})

    monkeypatch.setenv("AAC_ADMIN" + "_API_KEY", "strong-production-secret")
    settings = Settings(app_env="production", database_url="postgresql+asyncpg://u:p@host/db")
    assert settings.admin_api_key.get_secret_value() == "strong-production-secret"


def test_production_requires_explicit_database_url(monkeypatch) -> None:
    import pytest
    from pydantic import ValidationError

    monkeypatch.delenv("AAC_DATABASE_URL", raising=False)
    monkeypatch.setenv("AAC_ADMIN_API_KEY", "strong-production-secret")
    with pytest.raises(ValidationError, match="AAC_DATABASE_URL"):
        Settings(app_env="production")


def test_production_rejects_sqlite_database(monkeypatch) -> None:
    import pytest
    from pydantic import ValidationError

    monkeypatch.setenv("AAC_ADMIN_API_KEY", "strong-production-secret")
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(app_env="production", database_url="sqlite+aiosqlite:///./aac.db")


def test_postgres_engine_uses_connection_pool_health_checks() -> None:
    from app.core.config import database_engine_options

    settings = Settings(
        database_url="postgresql+asyncpg://u:p@host/database",
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


def test_sqlite_engine_does_not_receive_postgres_pool_options(monkeypatch) -> None:
    from app.core.config import database_engine_options

    monkeypatch.delenv("AAC_DATABASE_URL", raising=False)
    monkeypatch.delenv("AAC_APP_ENV", raising=False)
    assert database_engine_options(Settings()) == {"echo": False}
