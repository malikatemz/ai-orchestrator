import os
import platform
from typing import Any

from .config import settings


SAFE_ENV_KEYS = [
    "APP_ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "LOG_LEVEL",
    "SENTRY_TRACES_SAMPLE_RATE",
    "NEXT_PUBLIC_API_BASE_URL",
]


def redact_value(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if "KEY" in key or "TOKEN" in key or "SECRET" in key or "DSN" in key:
        return "[redacted]"
    if key == "DATABASE_URL":
        database_url = value or settings.database_url
        return database_url.split("@")[0] if "@" in database_url else database_url
    return value


def runtime_fingerprint() -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL") or settings.database_url
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "environment": os.getenv("APP_ENV", "development"),
        "database_driver": database_url.split("://")[0],
        "env": {
            key: redact_value(key, os.getenv(key))
            for key in SAFE_ENV_KEYS
            if os.getenv(key) is not None
        },
    }
