from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AAC_")

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./aac.db"
    api_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=list)
    auth_secret: SecretStr
    access_token_ttl_seconds: int = Field(default=86400, gt=0)
    admin_key: str = "dev-admin-key"  # AAC_ADMIN_KEY 환경변수로 오버라이드

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_admin_key(self) -> "Settings":
        if self.app_env == "production":
            if not self.admin_key or self.admin_key == "dev-admin-key":
                raise ValueError(
                    "AAC_ADMIN_KEY must be set to a secure non-default value in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
