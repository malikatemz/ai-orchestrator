"""Password hashing and verification using bcrypt.

This module provides secure password handling with bcrypt hashing.
Passwords are never stored in plaintext, only their bcrypt hashes.
"""

from typing import Tuple
import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Uses bcrypt with cost factor 12 for strong security while maintaining
    acceptable performance (typically <100ms per hash).

    Args:
        password: Plaintext password string (minimum 8 chars recommended)

    Returns:
        Bcrypt hash string suitable for storage in database

    Raises:
        ValueError: If password is empty or None

    Example:
        >>> hash1 = hash_password("MySecurePassword123!")
        >>> len(hash1) > 50  # Bcrypt hashes are long
        True
        >>> # Each call produces different hash (different salt)
        >>> hash2 = hash_password("MySecurePassword123!")
        >>> hash1 != hash2
        True
    """
    if not password:
        raise ValueError("Password cannot be empty")

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash.

    Safely compares plaintext password with stored bcrypt hash using
    constant-time comparison to prevent timing attacks.

    Args:
        plain_password: Plaintext password to check
        hashed_password: Stored bcrypt hash from database

    Returns:
        True if password matches hash, False otherwise

    Example:
        >>> password = "MySecurePassword123!"
        >>> hashed = hash_password(password)
        >>> verify_password(password, hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        # Return False for any verification errors (malformed hash, etc.)
        return False
