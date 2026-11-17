from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Validated, environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = (
        "postgresql+psycopg://connecthub_app:replace_me@127.0.0.1:5432/connecthub_dev"
    )
    test_database_url: str | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    session_cookie_name: str = "connecthub_session"
    csrf_cookie_name: str = "connecthub_csrf"
    csrf_secret: SecretStr | None = None
    session_lifetime_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    registration_rate_limit: int = Field(default=10, ge=1, le=1000)
    login_rate_limit: int = Field(default=20, ge=1, le=1000)
    room_create_rate_limit: int = Field(default=20, ge=1, le=1000)
    message_rate_limit: int = Field(default=30, ge=1, le=1000)
    websocket_connection_limit: int = Field(default=8, ge=1, le=100)
    websocket_queue_size: int = Field(default=100, ge=10, le=1000)
    websocket_frame_bytes: int = Field(default=16_384, ge=1024, le=65_536)
    websocket_malformed_limit: int = Field(default=3, ge=1, le=20)
    websocket_idle_timeout_seconds: int = Field(default=90, ge=15, le=600)
    typing_throttle_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    typing_expiry_seconds: int = Field(default=8, ge=2, le=60)
    invitation_lifetime_days: int = Field(default=7, ge=1, le=30)
    ai_enabled: bool = False
    ai_provider: Literal["gemini"] = "gemini"
    ai_api_key: SecretStr | None = None
    ai_text_model: str = "gemini-2.5-flash-lite"
    ai_embedding_model: str = "gemini-embedding-001"
    ai_embedding_dimensions: int = Field(default=768, ge=128, le=3072)
    ai_embedding_profile_version: str = "retrieval-v1"
    ai_auto_embed_new_messages: bool = False
    ai_backfill_enabled: bool = False
    ai_request_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    ai_max_summary_messages: int = Field(default=100, ge=1, le=500)
    ai_max_summary_characters: int = Field(default=24_000, ge=1_000, le=200_000)
    ai_summary_prompt_version: str = "summary-v1"
    ai_embedding_candidate_limit: int = Field(default=500, ge=10, le=2000)
    ai_embedding_max_attempts: int = Field(default=5, ge=1, le=20)
    ai_worker_poll_seconds: float = Field(default=2.0, ge=0.25, le=60.0)
    ai_stale_recovery_seconds: int = Field(default=60, ge=10, le=3600)

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def require_explicit_origins(cls, value: list[str]) -> list[str]:
        if not value or "*" in value:
            raise ValueError("ALLOWED_ORIGINS must contain explicit origins and never '*'")
        return value

    @field_validator("session_cookie_name", "csrf_cookie_name")
    @classmethod
    def require_cookie_name(cls, value: str) -> str:
        if not value or value.strip() != value or any(char in value for char in ";, \t\r\n"):
            raise ValueError("Cookie names must be non-empty HTTP token values")
        return value

    @field_validator(
        "ai_text_model",
        "ai_embedding_model",
        "ai_embedding_profile_version",
        "ai_summary_prompt_version",
    )
    @classmethod
    def require_safe_model_name(cls, value: str) -> str:
        if (
            not value
            or len(value) > 128
            or not all(char.isalnum() or char in "-_." for char in value)
        ):
            raise ValueError("AI model names may contain only letters, digits, '-', '_', and '.'")
        return value

    @model_validator(mode="after")
    def require_safe_production_cookies(self) -> "Settings":
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        return self

    def require_csrf_secret(self) -> bytes:
        if self.csrf_secret is None:
            raise RuntimeError("CSRF_SECRET is required to run the API")
        value = self.csrf_secret.get_secret_value()
        if len(value) < 32 or value.startswith("replace_"):
            raise RuntimeError(
                "CSRF_SECRET must be a non-placeholder value of at least 32 characters"
            )
        return value.encode()


@lru_cache
def get_settings() -> Settings:
    return Settings()
