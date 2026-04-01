from pydantic import Field

try:
    from pydantic_settings import BaseSettings
except ImportError:  # Pydantic v1 fallback
    from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Orchestrator"
    environment: str = "development"
    database_url: str = "sqlite:///./ai_orchestrator.db"
    redis_url: str = "redis://localhost:6379/0"
    api_token: str | None = None
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
