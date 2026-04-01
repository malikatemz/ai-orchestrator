import logging
import os
import sys
from typing import Any

import sentry_sdk
from pythonjsonlogger.json import JsonFormatter
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


def configure_logging() -> logging.Logger:
    """Configure JSON logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("ai_orchestrator")
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.handlers = [handler]
    logger.propagate = False
    return logger


from .config import settings

def initialize_sentry() -> None:
    """Initialize Sentry for error monitoring."""
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=settings.environment,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            CeleryIntegration(),
        ],
    )


def log_event(logger: logging.Logger, level: str, event: str, **context: Any) -> None:
    """Log an event with structured context."""
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(event, extra=context)
