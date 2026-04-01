from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    if settings.public_demo_mode:
        return {"sub": "demo-guest", "scopes": ["orchestrator:access", "orchestrator:demo"]}

    if settings.api_token is None:
        if settings.app_mode.value == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API token is not configured for this production environment.",
            )
        return {"sub": "admin", "scopes": ["orchestrator:access", "orchestrator:admin"]}

    if credentials and not hasattr(credentials, "scheme"):
        credentials = None

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid auth token")

    token = credentials.credentials
    if token != settings.api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token")

    return {"sub": "service-user", "scopes": ["orchestrator:access", "orchestrator:admin"]}

