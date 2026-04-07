"""Redis client for token blacklisting and session management.

This module manages Redis connections and provides methods for invalidating
tokens (logout), caching, and session state management.
"""

from datetime import timedelta
from typing import Optional

import redis

from .config import settings
from .observability import configure_logging

logger = configure_logging()

# Module-level Redis client (singleton)
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client connection.

    Lazily initializes Redis connection on first call. Returns None if
    Redis is unavailable (graceful degradation).

    Returns:
        Redis client instance or None if connection fails

    Example:
        >>> client = get_redis_client()
        >>> if client:
        ...     client.ping()  # Test connection
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = redis.from_url(str(settings.redis_url))
        _redis_client.ping()
        logger.info("Redis client initialized successfully")
        return _redis_client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {str(e)}")
        return None


def add_token_to_blacklist(
    token: str, expires_in_seconds: int = 3600
) -> bool:
    """Add JWT token to blacklist (logout).

    Stores token in Redis with expiration matching token's JWT exp claim.
    After expiration, token is automatically removed from Redis.

    Args:
        token: JWT token string to invalidate
        expires_in_seconds: Token expiration time in seconds (default: 1 hour)

    Returns:
        True if successfully blacklisted, False if Redis unavailable

    Example:
        >>> success = add_token_to_blacklist(token, expires_in_seconds=3600)
        >>> if success:
        ...     print("Token invalidated")
    """
    try:
        client = get_redis_client()
        if not client:
            logger.warning("Redis unavailable, token blacklist disabled")
            return False

        # Use token hash as key to save space
        token_key = f"blacklist:{hash(token)}"
        client.setex(token_key, timedelta(seconds=expires_in_seconds), "1")
        return True
    except Exception as e:
        logger.error(f"Failed to blacklist token: {str(e)}")
        return False


def is_token_blacklisted(token: str) -> bool:
    """Check if JWT token is blacklisted (logged out).

    Queries Redis to determine if token has been invalidated.
    Returns False if Redis unavailable (allow request to proceed).

    Args:
        token: JWT token string to check

    Returns:
        True if token is blacklisted, False if valid or Redis unavailable

    Example:
        >>> if is_token_blacklisted(token):
        ...     # Reject request with 401 Unauthorized
        ... else:
        ...     # Allow request to proceed
    """
    try:
        client = get_redis_client()
        if not client:
            # If Redis is down, allow requests (fail open)
            return False

        token_key = f"blacklist:{hash(token)}"
        return client.exists(token_key) > 0
    except Exception as e:
        logger.error(f"Failed to check token blacklist: {str(e)}")
        # Fail open if Redis is unavailable
        return False


def clear_blacklist() -> bool:
    """Clear all blacklisted tokens (admin operation).

    Removes all entries from blacklist. Used for testing or after
    credential compromise incident response.

    Returns:
        True if successful, False if Redis unavailable

    Example:
        >>> clear_blacklist()  # Remove all blacklisted tokens
        True
    """
    try:
        client = get_redis_client()
        if not client:
            return False

        # Delete all keys matching blacklist pattern
        keys = client.keys("blacklist:*")
        if keys:
            client.delete(*keys)
        return True
    except Exception as e:
        logger.error(f"Failed to clear blacklist: {str(e)}")
        return False
