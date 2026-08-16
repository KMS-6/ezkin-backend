from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AAC_")

    database_url: str = "sqlite+aiosqlite:///./aac.db"
    api_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=list)
    auth_secret: SecretStr
    access_token_ttl_seconds: int = Field(default=86400, gt=0)
    admin_api_key: SecretStr
    partner_api_key: SecretStr
    upload_dir: str = "./storage/uploads"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    idempotency_ttl_hours: int = Field(default=24, gt=0)

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
