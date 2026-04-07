from __future__ import annotations

import os
import secrets
from enum import Enum
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - Pydantic v1 fallback
    from pydantic import BaseSettings
    SettingsConfigDict = None

from pydantic import field_validator


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
    api_token: Optional[str] = None
    sentry_dsn: Optional[str] = None
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"
    public_demo_mode: bool = False
    auto_seed_demo: bool = False
    public_app_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    
    # Security settings
    secure_cookies: bool = True
    samesite_cookies: str = "strict"  # strict, lax, none
    
    # Stripe billing
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    
    # OAuth2 Configuration (Phase 5)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:3000/auth/google/callback"
    
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    github_redirect_uri: str = "http://localhost:3000/auth/github/callback"
    
    # JWT Configuration (Phase 5) - MUST be set in production
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_min_secret_length: int = 32
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # CORS and Security Headers
    enable_cors: bool = True
    cors_allow_credentials: bool = True
    cors_allow_headers: list = ["Content-Type", "Authorization"]
    cors_allow_methods: list = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    
    # Security headers
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000  # 1 year
    x_frame_options: str = "DENY"
    x_content_type_options: str = "nosniff"
    x_xss_protection: str = "1; mode=block"

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    else:  # pragma: no cover - Pydantic v1 fallback
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
    
    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: Optional[str], info) -> Optional[str]:
        """Validate JWT secret key has minimum length in production."""
        app_mode = info.data.get("app_mode", AppMode.DEVELOPMENT)
        
        # If not set, generate a random key for development
        if v is None:
            if app_mode == AppMode.PRODUCTION:
                raise ValueError(
                    "JWT_SECRET_KEY must be set in production. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            # Generate a random key for development
            return secrets.token_urlsafe(32)
        
        # Validate it's not the default insecure key
        if v == "your-super-secret-key-change-in-production":
            raise ValueError("JWT_SECRET_KEY is using the default insecure key. Must change in production.")
        
        # Validate minimum length
        if len(v) < 32:
            raise ValueError(f"JWT_SECRET_KEY must be at least 32 characters (got {len(v)})")
        
        return v
    
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def validate_origins(cls, v: str, info) -> str:
        """Validate allowed origins in production."""
        app_mode = info.data.get("app_mode", AppMode.DEVELOPMENT)
        
        if app_mode == AppMode.PRODUCTION and v == "*":
            raise ValueError(
                "ALLOWED_ORIGINS cannot be '*' in production. "
                "Specify exact origins (comma-separated): https://yourdomain.com,https://api.yourdomain.com"
            )
        return v

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
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_mode == AppMode.PRODUCTION or self.environment == "production"
    
    @property
    def is_https(self) -> bool:
        """Check if HTTPS should be required."""
        return self.public_api_url.startswith("https://") if self.is_production else False

    def validate_runtime(self) -> None:
        """Validate configuration at runtime."""
        # Check production security requirements
        if self.is_production:
            errors = []
            
            # Check HTTPS in production
            if not self.public_app_url.startswith("https://"):
                errors.append("PUBLIC_APP_URL must use HTTPS in production")
            if not self.public_api_url.startswith("https://"):
                errors.append("PUBLIC_API_URL must use HTTPS in production")
            
            # Check CORS is restrictive
            if self.allowed_origins == "*":
                errors.append("ALLOWED_ORIGINS cannot be '*' in production")
            
            # Check JWT secret is secure
            if not self.jwt_secret_key or len(self.jwt_secret_key) < 32:
                errors.append("JWT_SECRET_KEY must be set and at least 32 characters in production")
            
            # Check Stripe keys if billing is enabled
            # (they may not be required if billing is disabled)
            if self.stripe_secret_key and not self.stripe_secret_key.startswith("sk_live_"):
                errors.append("STRIPE_SECRET_KEY should use live key (sk_live_*) in production")
            
            if errors:
                raise RuntimeError(
                    "Production configuration validation failed:\n" + 
                    "\n".join(f"  - {error}" for error in errors)
                )
        
        # Check development defaults are not used in production
        if self.is_production and not self.public_demo_mode and not self.api_token:
            raise RuntimeError("API_TOKEN must be set in production unless PUBLIC_DEMO_MODE=true.")


settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
