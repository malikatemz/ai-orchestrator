"""JWT token generation, validation, and revocation"""

import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import redis

from ..config import get_settings
from ..models import User

logger = logging.getLogger(__name__)

settings = get_settings()

# Redis for revoked tokens
revoked_tokens_redis: Optional[redis.Redis] = None


def init_revoked_tokens_redis(redis_url: str) -> None:
    """Initialize Redis connection for token revocation"""
    global revoked_tokens_redis
    revoked_tokens_redis = redis.from_url(redis_url, decode_responses=True)


# ============ Token Creation ============

def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token (short-lived: 15 minutes).
    
    Payload includes user ID, email, role, org_id
    """
    settings = get_settings()
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "org_id": str(user.org_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    return token


def create_refresh_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token (long-lived: 7 days).
    
    Typically stored in secure httpOnly cookie.
    """
    settings = get_settings()
    
    if expires_delta is None:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)
    
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    
    payload = {
        "sub": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    return token


# ============ Token Validation ============

def decode_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    Decode and validate JWT.
    
    Raises jwt.InvalidTokenError if invalid/expired.
    """
    settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        # Check token type
        if payload.get("type") != token_type:
            raise jwt.InvalidTokenError(f"Wrong token type: expected {token_type}")
        
        # Check if revoked
        if token_type == "refresh" and is_token_revoked(token):
            raise jwt.InvalidTokenError("Token has been revoked")
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise jwt.InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise


# ============ Token Revocation ============

def revoke_token(token: str, token_type: str = "refresh") -> None:
    """
    Revoke a token (typically on logout).
    
    Stores in Redis with TTL = token expiration time.
    """
    if not revoked_tokens_redis:
        logger.warning("Redis not initialized for token revocation - skipping")
        return
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},  # Allow decoding expired tokens
        )
        
        exp = payload.get("exp")
        if exp:
            ttl = int(exp - datetime.now(timezone.utc).timestamp())
            if ttl > 0:
                revoked_tokens_redis.setex(f"revoked:{token}", ttl, "1")
                logger.info(f"Token revoked for user {payload.get('sub')}")
    
    except Exception as e:
        logger.error(f"Failed to revoke token: {str(e)}")


def is_token_revoked(token: str) -> bool:
    """Check if token has been revoked"""
    if not revoked_tokens_redis:
        return False
    
    return revoked_tokens_redis.exists(f"revoked:{token}") > 0


# ============ Token Refresh ============

def refresh_access_token(refresh_token: str, db: Session) -> str:
    """
    Exchange a refresh token for a new access token.
    
    Returns new access token (short-lived).
    """
    try:
        payload = decode_token(refresh_token, token_type="refresh")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid refresh token: {str(e)}")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise ValueError(f"User not found: {user_id}")
    
    return create_access_token(user)
