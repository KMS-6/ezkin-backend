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
    admin_api_key: SecretStr
    partner_api_key: SecretStr
    upload_dir: str = "./storage/uploads"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    idempotency_ttl_hours: int = Field(default=24, gt=0)
    # 챗봇 10.2/10.5절: parse_confidence < 0.60일 때만 쓰는 저비용 LLM escalation.
    # 키가 없으면 기능이 조용히 꺼지고 규칙 기반 결과로만 동작한다(17절 가용성 원칙).
    anthropic_api_key: SecretStr | None = None
    chat_llm_model: str = "claude-haiku-4-5"
    # Vision AI Input 5절: 카메라 스캔 관찰값 생성용 멀티모달 모델. 키가 없으면 이
    # 기능은 조용히 꺼지고 기존 model_not_implemented 폴백으로 동작한다(17절 가용성
    # 원칙). 챗봇 escalation(anthropic_api_key)과는 별도 provider/키를 쓴다.
    openai_api_key: SecretStr | None = None
    vision_llm_model: str = "gpt-4o-mini"
    # 페르소나당 하루 escalation 호출 상한 — 애매한 메시지가 몰려도 비용이 무한정
    # 늘어나지 않게 막는 안전장치. 초과하면 escalation 없이 규칙 기반 결과로 폴백한다.
    chat_llm_daily_cap_per_persona: int = Field(default=20, ge=0)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
