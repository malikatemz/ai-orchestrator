import os
import platform
from typing import Any

from .models import DATABASE_URL


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
        return DATABASE_URL.split("@")[0] if "@" in DATABASE_URL else DATABASE_URL
    return value


def runtime_fingerprint() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "environment": os.getenv("APP_ENV", "development"),
        "database_driver": DATABASE_URL.split("://")[0],
        "env": {
            key: redact_value(key, os.getenv(key))
            for key in SAFE_ENV_KEYS
            if os.getenv(key) is not None
        },
    }
