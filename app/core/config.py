from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AAC_")

    environment: Literal["local", "test", "production"] = "local"
    database_url: str = "sqlite+aiosqlite:///./aac.db"
    database_pool_size: int = Field(default=5, gt=0)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout: int = Field(default=30, gt=0)
    database_pool_recycle: int = Field(default=1800, gt=0)
    api_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=list)
    auth_secret: SecretStr
    access_token_ttl_seconds: int = Field(default=86400, gt=0)

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def require_postgres_in_production(self) -> "Settings":
        if self.environment != "production":
            return self
        if "database_url" not in self.model_fields_set:
            raise ValueError("AAC_DATABASE_URL is required in production")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("production DATABASE_URL must use PostgreSQL")
        return self


def database_engine_options(settings: Settings) -> dict[str, object]:
    options: dict[str, object] = {"echo": settings.debug}
    if settings.database_url.startswith("postgresql+asyncpg://"):
        options.update(
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_recycle=settings.database_pool_recycle,
        )
    return options


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
