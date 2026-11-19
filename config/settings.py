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
    policy_storage_bucket: str = "refund-policies"
    policy_top_k: int = 4
    policy_min_similarity: float = 0.25
    policy_chunk_size: int = 1000
    policy_chunk_overlap: int = 150

    @field_validator("policy_top_k", "policy_chunk_size")
    @classmethod
    def positive_policy_setting(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Policy top-k and chunk size must be positive")
        return value

    @field_validator("policy_chunk_overlap")
    @classmethod
    def nonnegative_policy_overlap(cls, value: int) -> int:
        if value < 0:
            raise ValueError("POLICY_CHUNK_OVERLAP must not be negative")
        return value

    @field_validator("policy_min_similarity")
    @classmethod
    def valid_policy_similarity(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("POLICY_MIN_SIMILARITY must be between 0 and 1")
        return value

    @field_validator("refund_window_days")
    @classmethod
    def positive_refund_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("REFUND_WINDOW_DAYS must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
