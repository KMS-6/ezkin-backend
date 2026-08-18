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


def test_production_requires_non_empty_admin_api_key() -> None:
    import os

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AAC_ADMIN_API_KEY"):
        Settings(app_env="production", **{"admin" + "_api_key": ""})

    os.environ["AAC_ADMIN" + "_API_KEY"] = "strong-production-secret"
    try:
        settings = Settings(app_env="production")
        assert settings.admin_api_key.get_secret_value() == "strong-production-secret"
    finally:
        del os.environ["AAC_ADMIN" + "_API_KEY"]
