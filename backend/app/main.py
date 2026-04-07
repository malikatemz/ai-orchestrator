from __future__ import annotations

from contextlib import asynccontextmanager
import uuid

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import settings
from .database import SessionLocal, init_db
from .error_handling import ApiError, ErrorCode, ErrorSeverity
from .observability import configure_logging, initialize_sentry
from .rate_limiter import maybe_rate_limit
from .routes import router
from .routes_billing import router as billing_router
from .services import seed_demo_data
from .security import configure_security
import redis

initialize_sentry()
logger = configure_logging()

def run_startup_tasks() -> None:
    settings.validate_runtime()
    if settings.should_auto_init_db:
        init_db()

    # Test Redis connection for OAuth state storage
    try:
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        logger.info("Redis connection successful - OAuth state tracking enabled")
    except Exception as e:
        logger.warning(f"Redis connection failed: {str(e)} - OAuth state tracking disabled")

    if settings.should_auto_seed_demo:
        db = SessionLocal()
        try:
            seed_demo_data(db, force=False, actor="system")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_startup_tasks()
    yield


app = FastAPI(title=settings.app_name, version="1.1.0", lifespan=lifespan)

# Configure security (CORS, headers, etc.)
configure_security(app, settings)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    maybe_rate_limit(request)
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError):
    payload = exc.as_payload()
    payload["request_id"] = request.state.request_id
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    error = ApiError(
        code=ErrorCode.INVALID_REQUEST if exc.status_code < 500 else ErrorCode.INTERNAL_ERROR,
        message=str(exc.detail),
        status_code=exc.status_code,
        severity=ErrorSeverity.LOW if exc.status_code < 500 else ErrorSeverity.HIGH,
        retryable=exc.status_code >= 500,
    )
    return await handle_api_error(request, error)


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(request: Request, exc: RequestValidationError):
    error = ApiError(
        code=ErrorCode.INVALID_REQUEST,
        message="Request validation failed.",
        status_code=422,
        severity=ErrorSeverity.LOW,
        retryable=False,
        details={"errors": exc.errors()},
    )
    return await handle_api_error(request, error)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("unhandled_exception", extra={"request_id": request.state.request_id, "path": str(request.url.path)})
    sentry_sdk.capture_exception(exc)
    error = ApiError(
        code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected system error occurred.",
        status_code=500,
        severity=ErrorSeverity.HIGH,
        retryable=True,
    )
    return await handle_api_error(request, error)


def on_startup() -> None:
    run_startup_tasks()


app.include_router(router)
app.include_router(billing_router)
