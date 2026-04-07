"""JWT authentication module for token generation and validation.

This module provides JWT (JSON Web Token) functionality for authentication
and session management. Tokens include custom claims for user context and
can be refreshed or invalidated.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import jwt
from pydantic import BaseModel

from .config import settings
from .observability import configure_logging

logger = configure_logging()

# Algorithm and key
ALGORITHM: str = "HS256"
SECRET_KEY: str = str(settings.jwt_secret_key or "dev-secret-key")


class TokenPayload(BaseModel):
    """JWT token payload schema.
    
    Attributes:
        user_id: Unique user identifier
        workspace_id: Workspace the token is scoped to
        role: User's role in the workspace
        exp: Token expiration timestamp (Unix seconds)
        iat: Token issue timestamp (Unix seconds)
    """

    user_id: str
    workspace_id: str
    role: str
    exp: int
    iat: int


def generate_token(
    user_id: str,
    workspace_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate JWT access token with custom claims.

    Creates a signed JWT token with user context and expiration. Tokens
    can be refreshed via the refresh endpoint or invalidated via logout.

    Args:
        user_id: Unique user identifier
        workspace_id: Workspace this token is scoped to
        role: User's role in the workspace (owner, admin, operator, viewer)
        expires_delta: Optional custom expiration delta. Defaults to
            settings.access_token_expire_minutes (15 mins by default)

    Returns:
        Signed JWT token as string

    Raises:
        ValueError: If user_id, workspace_id, or role is empty

    Example:
        >>> token = generate_token(
        ...     user_id="user-abc123",
        ...     workspace_id="ws-xyz789",
        ...     role="operator"
        ... )
        >>> len(token) > 50  # JWT tokens are long
        True
    """
    if not user_id or not workspace_id or not role:
        raise ValueError("user_id, workspace_id, and role are required")

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=int(settings.access_token_expire_minutes or 15)
        )

    now_timestamp = int(time.time())
    expire_timestamp = now_timestamp + int(expires_delta.total_seconds())

    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "role": role,
        "exp": expire_timestamp,
        "iat": now_timestamp,
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def validate_token(token: str) -> Tuple[bool, Optional[TokenPayload], Optional[str]]:
    """Validate JWT access token and extract claims.

    Verifies token signature and expiration. Returns claims if valid,
    otherwise returns error message.

    Args:
        token: JWT token string to validate

    Returns:
        Tuple of (is_valid, payload, error_message):
            - is_valid: True if token is valid and not expired
            - payload: TokenPayload if valid, None if invalid
            - error_message: Error description if invalid, None if valid

    Example:
        >>> is_valid, payload, error = validate_token(token)
        >>> if is_valid:
        ...     print(f"Token for user {payload.user_id} in workspace {payload.workspace_id}")
        ... else:
        ...     print(f"Invalid token: {error}")
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_payload = TokenPayload(**payload)
        return True, token_payload, None
    except jwt.ExpiredSignatureError:
        return False, None, "Token has expired"
    except jwt.InvalidTokenError as e:
        return False, None, f"Invalid token: {str(e)}"
    except (ValueError, KeyError) as e:
        return False, None, f"Token missing required claims: {str(e)}"


def refresh_token(
    user_id: str,
    workspace_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Refresh JWT token with new expiration.

    Creates a new token with the same claims but updated expiration.
    Used when client sends a refresh token or before expiration.

    Args:
        user_id: Unique user identifier
        workspace_id: Workspace this token is scoped to
        role: User's role in the workspace
        expires_delta: Optional custom expiration delta

    Returns:
        New signed JWT token

    Raises:
        ValueError: If user_id, workspace_id, or role is empty

    Example:
        >>> old_token = generate_token(user_id, workspace_id, role)
        >>> new_token = refresh_token(user_id, workspace_id, role)
        >>> old_token != new_token  # Different tokens
        True
    """
    return generate_token(user_id, workspace_id, role, expires_delta)


def extract_token_from_header(authorization: str) -> Optional[str]:
    """Extract JWT token from Authorization header.

    Parses "Bearer <token>" format from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        Token string if valid format, None if invalid

    Example:
        >>> token = extract_token_from_header("Bearer eyJhbGc...")
        >>> token
        "eyJhbGc..."
        >>> extract_token_from_header("Basic xyz") is None
        True
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]

    return None
