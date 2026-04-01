from typing import Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Authenticate and return current user info from bearer token."""
    if settings.api_token is None:
        return {"sub": "admin", "scopes": ["orchestrator:access", "orchestrator:admin"]}

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid auth token")

    token = credentials.credentials
    if token != settings.api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token")

    return {"sub": "service-user", "scopes": ["orchestrator:access"]}
