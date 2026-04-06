from __future__ import annotations

from enum import Enum

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - Pydantic v1 fallback
    from pydantic import BaseSettings
    SettingsConfigDict = None


class AppMode(str, Enum):
    DEVELOPMENT = "development"
    DEMO = "demo"
    PRODUCTION = "production"


class Settings(BaseSettings):
    app_name: str = "AI Orchestrator"
    environment: str = "development"
    app_mode: AppMode = AppMode.DEVELOPMENT
    database_url: str = "sqlite:///./ai_orchestrator.db"
    redis_url: str = "redis://localhost:6379/0"
    api_token: str | None = None
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    allowed_origins: str = "*"
    public_demo_mode: bool = False
    auto_seed_demo: bool = False
    public_app_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    
    # Stripe billing
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    else:  # pragma: no cover - Pydantic v1 fallback
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_demo_mode(self) -> bool:
        return self.app_mode == AppMode.DEMO or self.public_demo_mode

    @property
    def auth_required(self) -> bool:
        if self.public_demo_mode:
            return False
        return bool(self.api_token)

    @property
    def should_auto_seed_demo(self) -> bool:
        return self.auto_seed_demo and self.is_demo_mode

    @property
    def should_auto_init_db(self) -> bool:
        return self.app_mode != AppMode.PRODUCTION or self.database_url.startswith("sqlite")

    def validate_runtime(self) -> None:
        if self.app_mode == AppMode.PRODUCTION and not self.public_demo_mode and not self.api_token:
            raise RuntimeError("API_TOKEN must be set in production unless PUBLIC_DEMO_MODE=true.")


settings = Settings()
