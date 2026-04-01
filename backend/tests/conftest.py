from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app import main, models, routes
from app.auth import get_current_user


@pytest.fixture
def test_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.db"
    engine = models.build_engine(f"sqlite:///{database_path}")
    session_factory = models.build_session_factory(engine)
    models.init_db(engine)

    monkeypatch.setattr(models, "engine", engine)
    monkeypatch.setattr(models, "SessionLocal", session_factory)
    monkeypatch.setattr(routes, "SessionLocal", session_factory)
    monkeypatch.setattr(main, "maybe_rate_limit", lambda request: None)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[routes.get_db] = override_get_db
    main.app.dependency_overrides[get_current_user] = lambda: {"sub": "admin", "scopes": ["orchestrator:access", "orchestrator:admin"]}

    with TestClient(main.app) as client:
        yield client

    main.app.dependency_overrides.clear()
