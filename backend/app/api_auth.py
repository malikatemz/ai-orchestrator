from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    """Authenticate HTTP request and return user context.
    
    Validates Bearer token or returns demo user context. Supports three authentication modes:
    
    1. **Public Demo Mode** (settings.public_demo_mode=True)
       - No credentials required, returns demo-guest user
       - Useful for onboarding and public demos
       - Scopes: orchestrator:access, orchestrator:demo (read-only)
    
    2. **Development Mode** (settings.api_token=None, app_mode != production)
       - No credentials required, returns admin user
       - Useful for local development and testing
       - Scopes: orchestrator:access, orchestrator:admin (full access)
    
    3. **Production Mode** (settings.api_token set)
       - Requires valid Bearer token matching settings.api_token
       - Raises 401 Unauthorized if missing or invalid
       - Service accounts use this mode
    
    Args:
        credentials: Optional HTTP Bearer credentials from request header.
            Format: Authorization: Bearer <token>
            If present, scheme must be "bearer" (case-insensitive)
    
    Returns:
        User context dictionary with keys:
        - sub: Subject/user ID (demo-guest, admin, or service-user)
        - scopes: List of granted scopes for authorization checks
    
    Raises:
        HTTPException(401): If credentials invalid or token mismatch
        HTTPException(503): If production mode with no API token configured
    
    Status Codes:
        - 401 (Unauthorized): Invalid or missing credentials
        - 503 (Service Unavailable): Production mode misconfigured
        - 200 (implicit): Valid credentials, user context returned
    
    User Contexts Returned:
        >>> # Demo mode
        >>> {"sub": "demo-guest", "scopes": ["orchestrator:access", "orchestrator:demo"]}
        >>> # Development mode
        >>> {"sub": "admin", "scopes": ["orchestrator:access", "orchestrator:admin"]}
        >>> # Production mode (valid token)
        >>> {"sub": "service-user", "scopes": ["orchestrator:access", "orchestrator:admin"]}
    
    Example:
        >>> # Using in a route
        >>> @app.get("/workflows")
        >>> async def list_workflows(current_user=Depends(get_current_user)):
        ...     # current_user is validated and populated here
        ...     user_id = current_user["sub"]
        ...     scopes = current_user["scopes"]
        ...     # Proceed with authorization checks
    
    Authorization Pattern:
        Consumers should check user context for required scopes:
        >>> def ensure_admin(current_user):
        ...     if "orchestrator:admin" not in current_user.get("scopes", []):
        ...         raise PermissionError("Admin access required")
    
    Security Notes:
        - In production, API tokens should be stored in secure environment variables
        - Bearer tokens are validated with simple string comparison (suitable for single token)
        - For multi-user systems, integrate with OAuth2 or JWT providers
        - Scheme must be lowercase "bearer" (HTTP spec)
    """
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
