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


def test_production_requires_non_default_admin_key() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AAC_ADMIN_KEY"):
        Settings(app_env="production", admin_key="dev-admin-key")

    with pytest.raises(ValidationError, match="AAC_ADMIN_KEY"):
        Settings(app_env="production", admin_key="")

    settings = Settings(app_env="production", admin_key="strong-production-secret-key")
    assert settings.admin_key == "strong-production-secret-key"
