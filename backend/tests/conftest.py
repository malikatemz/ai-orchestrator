from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import main
from app.api_auth import get_current_user
from app.config import AppMode, settings
from app.database import build_engine, build_session, get_db, init_db


@pytest.fixture(autouse=True)
def reset_settings():
    original = {
        "app_mode": settings.app_mode,
        "public_demo_mode": settings.public_demo_mode,
        "auto_seed_demo": settings.auto_seed_demo,
        "api_token": settings.api_token,
        "allowed_origins": settings.allowed_origins,
        "public_app_url": settings.public_app_url,
        "public_api_url": settings.public_api_url,
    }
    yield
    for key, value in original.items():
        setattr(settings, key, value)


@pytest.fixture
def test_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.db"
    engine = build_engine(f"sqlite:///{database_path}")
    session_factory = build_session(engine)
    init_db(engine)

    monkeypatch.setattr(main, "maybe_rate_limit", lambda request: None)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    monkeypatch.setattr("app.database.engine", engine)
    monkeypatch.setattr("app.database.SessionLocal", session_factory)
    monkeypatch.setattr("app.worker.SessionLocal", session_factory)

    settings.app_mode = AppMode.DEVELOPMENT
    settings.public_demo_mode = False
    settings.auto_seed_demo = False
    settings.api_token = None
    settings.allowed_origins = "*"

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin",
        "scopes": ["orchestrator:access", "orchestrator:admin"],
        "org_id": "test_org",
        "role": "owner"
    }

    with TestClient(main.app) as client:
        yield client

    main.app.dependency_overrides.clear()


@pytest.fixture
def test_db(tmp_path, monkeypatch) -> Generator[Session, None, None]:
    """Provides a test database session"""
    database_path = tmp_path / "test.db"
    engine = build_engine(f"sqlite:///{database_path}")
    session_factory = build_session(engine)
    init_db(engine)

    db = session_factory()
    try:
        yield db
    finally:
        db.close()
