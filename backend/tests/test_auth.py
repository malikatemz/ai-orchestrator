from fastapi import HTTPException

from app import api_auth as auth


class Credentials:
    def __init__(self, scheme: str, credentials: str):
        self.scheme = scheme
        self.credentials = credentials


class TestGetCurrentUser:
    def test_it_returns_admin_context_when_api_token_is_not_configured(self, monkeypatch):
        monkeypatch.setattr(auth.settings, "api_token", None)

        payload = auth.get_current_user()

        assert payload["sub"] == "admin"
        assert "orchestrator:admin" in payload["scopes"]

    def test_it_accepts_valid_bearer_tokens(self, monkeypatch):
        monkeypatch.setattr(auth.settings, "api_token", "secret-token")

        payload = auth.get_current_user(Credentials("Bearer", "secret-token"))

        assert payload["sub"] == "service-user"
        assert payload["scopes"] == ["orchestrator:access", "orchestrator:admin"]

    def test_it_rejects_missing_credentials_when_auth_is_enabled(self, monkeypatch):
        monkeypatch.setattr(auth.settings, "api_token", "secret-token")

        try:
            auth.get_current_user()
            raised = None
        except HTTPException as exc:
            raised = exc

        assert raised is not None
        assert raised.status_code == 401

    def test_it_rejects_invalid_tokens(self, monkeypatch):
        monkeypatch.setattr(auth.settings, "api_token", "secret-token")

        try:
            auth.get_current_user(Credentials("Bearer", "wrong-token"))
            raised = None
        except HTTPException as exc:
            raised = exc

        assert raised is not None
        assert raised.status_code == 401
