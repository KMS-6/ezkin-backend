from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AAC_")

    app_env: str = "development"
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
    admin_api_key: SecretStr
    partner_api_key: SecretStr
    upload_dir: str = "./storage/uploads"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    idempotency_ttl_hours: int = Field(default=24, gt=0)
    # 챗봇 10.2/10.5절: parse_confidence < 0.60일 때만 쓰는 저비용 LLM escalation.
    # 키가 없으면 기능이 조용히 꺼지고 규칙 기반 결과로만 동작한다(17절 가용성 원칙).
    openai_api_key: SecretStr | None = None
    chat_llm_model: str = "gpt-5.4-mini"
    # Vision AI Input 5절: 카메라 스캔 관찰값 생성용 멀티모달 모델. OpenAI 키가
    # 없으면 기능이 조용히 꺼지고 기존 model_not_implemented 폴백으로 동작한다.
    vision_llm_model: str = "gpt-5.4-mini"
    # 페르소나당 하루 escalation 호출 상한 — 애매한 메시지가 몰려도 비용이 무한정
    # 늘어나지 않게 막는 안전장치. 초과하면 escalation 없이 규칙 기반 결과로 폴백한다.
    chat_llm_daily_cap_per_persona: int = Field(default=20, ge=0)
    # Report/Briefing 5.7/5.8절: 계산된 사실만 재문장화하는 선택적 LLM. Anthropic 키가
    # 없으면 기능이 조용히 꺼지고 규칙 기반 템플릿 summary로만 동작한다.
    narration_llm_model: str = "gpt-5.4-mini"
    # ADR 003: 기상청 공공데이터포털 연동. 키가 없거나 호출이 실패하면 조용히
    # 꺼지고 기존처럼 날씨 요인이 생략된다(임의 날씨 생성 금지).
    weather_api_key: SecretStr | None = None
    weather_cache_ttl_minutes: int = Field(default=60, gt=0)

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_admin_key(self) -> "Settings":
        if self.app_env == "production":
            key = self.admin_api_key.get_secret_value()
            if not key:
                raise ValueError(
                    "AAC_ADMIN_API_KEY must be set to a secure non-default value in production"
                )
        return self

    @model_validator(mode="after")
    def require_postgres_in_production(self) -> "Settings":
        if self.app_env != "production":
            return self
        if "database_url" not in self.model_fields_set:
            raise ValueError("AAC_DATABASE_URL is required in production")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("production DATABASE_URL must use PostgreSQL")
        return self


def database_engine_options(settings: "Settings") -> dict[str, object]:
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
