from functools import lru_cache
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: SecretStr
    groq_model: str = "llama-3.3-70b-versatile"
    supabase_url: str
    supabase_secret_key: SecretStr
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "refund-agent"
    langsmith_tracing: bool = False
    refund_window_days: int = 30
    frontend_origin: str = "http://localhost:5173"

    @field_validator("refund_window_days")
    @classmethod
    def positive_refund_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("REFUND_WINDOW_DAYS must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
