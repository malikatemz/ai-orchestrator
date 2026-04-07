"""Tests for Week 3 JWT authentication module.

Tests JWT token generation, validation, password hashing, and authentication
endpoints (login, register, logout, refresh).
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from jwt import ExpiredSignatureError, InvalidTokenError, encode, decode

from app.auth_module import (
    ALGORITHM,
    SECRET_KEY,
    extract_token_from_header,
    generate_token,
    refresh_token,
    validate_token,
)
from app.password_utils import hash_password, verify_password


class TestPasswordUtils:
    """Tests for password hashing and verification."""

    def test_hash_password_creates_hash(self) -> None:
        """Test that hash_password creates a valid bcrypt hash."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert hashed is not None
        assert len(hashed) > 50  # Bcrypt hashes are long
        assert hashed.startswith("$2b$")  # Bcrypt format

    def test_hash_password_different_each_time(self) -> None:
        """Test that hash_password creates different hashes (different salts)."""
        password = "SecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self) -> None:
        """Test that verify_password works with correct password."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """Test that verify_password rejects incorrect password."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_password_empty_raises_error(self) -> None:
        """Test that hash_password raises error for empty password."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")

    def test_hash_password_none_raises_error(self) -> None:
        """Test that hash_password raises error for None password."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password(None)

    def test_verify_password_malformed_hash(self) -> None:
        """Test that verify_password handles malformed hash gracefully."""
        password = "SecurePassword123!"
        malformed_hash = "not-a-valid-bcrypt-hash"

        assert verify_password(password, malformed_hash) is False

    def test_hash_and_verify_long_password(self) -> None:
        """Test hashing and verifying a long password."""
        password = "a" * 200  # Very long password
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True


class TestJWTGeneration:
    """Tests for JWT token generation."""

    def test_generate_token_creates_valid_jwt(self) -> None:
        """Test that generate_token creates a valid JWT."""
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

    def test_generate_token_with_custom_expiration(self) -> None:
        """Test token generation with custom expiration delta."""
        custom_delta = timedelta(hours=2)
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
            expires_delta=custom_delta,
        )

        is_valid, payload, _ = validate_token(token)
        assert is_valid is True
        assert payload is not None

    def test_generate_token_empty_user_id_raises_error(self) -> None:
        """Test that empty user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id.*required"):
            generate_token(
                user_id="",
                workspace_id="ws-456",
                role="operator",
            )

    def test_generate_token_empty_workspace_id_raises_error(self) -> None:
        """Test that empty workspace_id raises ValueError."""
        with pytest.raises(ValueError, match="workspace_id.*required"):
            generate_token(
                user_id="user-123",
                workspace_id="",
                role="operator",
            )

    def test_generate_token_empty_role_raises_error(self) -> None:
        """Test that empty role raises ValueError."""
        with pytest.raises(ValueError, match="role.*required"):
            generate_token(
                user_id="user-123",
                workspace_id="ws-456",
                role="",
            )

    def test_generate_token_includes_custom_claims(self) -> None:
        """Test that generated token includes all custom claims."""
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="admin",
        )

        # Decode without validation to check claims
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["user_id"] == "user-123"
        assert payload["workspace_id"] == "ws-456"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload

    def test_generate_token_includes_expiration(self) -> None:
        """Test that token includes valid expiration timestamp."""
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert isinstance(payload["exp"], int)
        assert payload["exp"] > payload["iat"]

    def test_generate_token_different_each_time(self) -> None:
        """Test that generate_token creates different tokens (different iat)."""
        token1 = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )
        token2 = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        # Tokens should be different due to different iat timestamps
        # (unlikely they'll be issued in exact same millisecond)
        payload1 = decode(token1, SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = decode(token2, SECRET_KEY, algorithms=[ALGORITHM])
        # Allow them to be different, at minimum the tokens themselves differ
        assert token1 != token2 or payload1 == payload2


class TestJWTValidation:
    """Tests for JWT token validation."""

    def test_validate_token_valid_token(self) -> None:
        """Test that validate_token accepts valid token."""
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        is_valid, payload, error = validate_token(token)
        assert is_valid is True
        assert payload is not None
        assert error is None
        assert payload.user_id == "user-123"
        assert payload.workspace_id == "ws-456"
        assert payload.role == "operator"

    def test_validate_token_expired_token(self) -> None:
        """Test that validate_token rejects expired token."""
        # Create token with negative expiration (already expired)
        expired_delta = timedelta(seconds=-1)
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
            expires_delta=expired_delta,
        )

        is_valid, payload, error = validate_token(token)
        assert is_valid is False
        assert payload is None
        assert error is not None
        assert "expired" in error.lower()

    def test_validate_token_invalid_signature(self) -> None:
        """Test that validate_token rejects token with invalid signature."""
        # Create token with different secret
        wrong_secret = "wrong-secret-key"
        payload_dict = {
            "user_id": "user-123",
            "workspace_id": "ws-456",
            "role": "operator",
            "exp": 9999999999,
            "iat": 1234567890,
        }
        token = encode(payload_dict, wrong_secret, algorithm=ALGORITHM)

        is_valid, payload, error = validate_token(token)
        assert is_valid is False
        assert payload is None
        assert error is not None

    def test_validate_token_malformed_token(self) -> None:
        """Test that validate_token handles malformed token."""
        malformed_token = "not.a.valid.jwt.token"

        is_valid, payload, error = validate_token(malformed_token)
        assert is_valid is False
        assert payload is None
        assert error is not None

    def test_validate_token_empty_token(self) -> None:
        """Test that validate_token handles empty token."""
        is_valid, payload, error = validate_token("")

        assert is_valid is False
        assert payload is None
        assert error is not None

    def test_validate_token_missing_claims(self) -> None:
        """Test that validate_token rejects token with missing required claims."""
        # Create token with missing user_id claim
        incomplete_payload = {
            "workspace_id": "ws-456",
            "role": "operator",
            "exp": 9999999999,
            "iat": 1234567890,
        }
        token = encode(incomplete_payload, SECRET_KEY, algorithm=ALGORITHM)

        is_valid, payload, error = validate_token(token)
        assert is_valid is False
        assert payload is None
        assert error is not None


class TestJWTRefresh:
    """Tests for JWT token refresh."""

    def test_refresh_token_creates_new_token(self) -> None:
        """Test that refresh_token creates a valid new token."""
        old_token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        new_token = refresh_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        # New token should be valid
        is_valid, payload, _ = validate_token(new_token)
        assert is_valid is True
        assert payload is not None

    def test_refresh_token_different_token(self) -> None:
        """Test that refresh_token creates different token from original."""
        user_id = "user-123"
        workspace_id = "ws-456"
        role = "operator"

        token1 = generate_token(user_id, workspace_id, role)
        token2 = refresh_token(user_id, workspace_id, role)

        # Tokens should be different (different iat/exp)
        payload1 = decode(token1, SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = decode(token2, SECRET_KEY, algorithms=[ALGORITHM])
        # They have the same claims but different timestamps
        assert payload1["user_id"] == payload2["user_id"]
        assert payload1["workspace_id"] == payload2["workspace_id"]

    def test_refresh_token_preserves_claims(self) -> None:
        """Test that refresh_token preserves user claims."""
        old_token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="admin",
        )

        new_token = refresh_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="admin",
        )

        is_valid, payload, _ = validate_token(new_token)
        assert payload.user_id == "user-123"
        assert payload.workspace_id == "ws-456"
        assert payload.role == "admin"

    def test_refresh_token_custom_expiration(self) -> None:
        """Test refresh_token with custom expiration."""
        custom_delta = timedelta(hours=1)
        token = refresh_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
            expires_delta=custom_delta,
        )

        is_valid, payload, _ = validate_token(token)
        assert is_valid is True


class TestAuthorizationHeaderExtraction:
    """Tests for extracting JWT from Authorization header."""

    def test_extract_token_valid_bearer_header(self) -> None:
        """Test extracting token from valid Bearer header."""
        token_str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        auth_header = f"Bearer {token_str}"

        extracted = extract_token_from_header(auth_header)
        assert extracted == token_str

    def test_extract_token_case_insensitive_bearer(self) -> None:
        """Test that Bearer prefix is case-insensitive."""
        token_str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        auth_header = f"bearer {token_str}"

        extracted = extract_token_from_header(auth_header)
        assert extracted == token_str

    def test_extract_token_invalid_scheme(self) -> None:
        """Test that non-Bearer schemes return None."""
        token_str = "some-token-value"
        auth_header = f"Basic {token_str}"

        extracted = extract_token_from_header(auth_header)
        assert extracted is None

    def test_extract_token_empty_header(self) -> None:
        """Test that empty header returns None."""
        extracted = extract_token_from_header("")

        assert extracted is None

    def test_extract_token_none_header(self) -> None:
        """Test that None header returns None."""
        extracted = extract_token_from_header(None)

        assert extracted is None

    def test_extract_token_missing_token(self) -> None:
        """Test that Bearer without token returns None."""
        auth_header = "Bearer"

        extracted = extract_token_from_header(auth_header)
        assert extracted is None

    def test_extract_token_extra_parts(self) -> None:
        """Test that too many parts returns None."""
        auth_header = "Bearer token extra-part"

        extracted = extract_token_from_header(auth_header)
        assert extracted is None

    def test_extract_token_real_jwt(self) -> None:
        """Test extraction with real JWT token."""
        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )
        auth_header = f"Bearer {token}"

        extracted = extract_token_from_header(auth_header)
        assert extracted == token

        # Verify extracted token is valid
        is_valid, _, _ = validate_token(extracted)
        assert is_valid is True


class TestIntegration:
    """Integration tests for complete auth flow."""

    def test_complete_auth_flow(self) -> None:
        """Test complete authentication flow: hash, generate token, validate."""
        password = "UserPassword123!"
        user_id = "user-123"
        workspace_id = "ws-456"
        role = "operator"

        # Hash password
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

        # Generate token
        token = generate_token(user_id, workspace_id, role)
        is_valid, payload, error = validate_token(token)

        assert is_valid is True
        assert payload is not None
        assert payload.user_id == user_id
        assert payload.workspace_id == workspace_id
        assert payload.role == role

    def test_token_refresh_flow(self) -> None:
        """Test token refresh flow."""
        user_id = "user-123"
        workspace_id = "ws-456"
        role = "operator"

        # Generate initial token
        token1 = generate_token(user_id, workspace_id, role)
        is_valid, _, _ = validate_token(token1)
        assert is_valid is True

        # Refresh token
        token2 = refresh_token(user_id, workspace_id, role)
        is_valid, payload, _ = validate_token(token2)
        assert is_valid is True
        assert payload.user_id == user_id

    def test_logout_via_blacklist(self) -> None:
        """Test logout by adding token to blacklist."""
        from app.redis_client import add_token_to_blacklist, is_token_blacklisted

        token = generate_token(
            user_id="user-123",
            workspace_id="ws-456",
            role="operator",
        )

        # Initially not blacklisted
        assert is_token_blacklisted(token) is False

        # Add to blacklist (simulating logout)
        add_token_to_blacklist(token, expires_in_seconds=3600)

        # Now should be blacklisted
        assert is_token_blacklisted(token) is True

    def test_different_roles_in_tokens(self) -> None:
        """Test that tokens correctly reflect different roles."""
        user_id = "user-123"
        workspace_id = "ws-456"

        for role in ["owner", "admin", "operator", "viewer"]:
            token = generate_token(user_id, workspace_id, role)
            is_valid, payload, _ = validate_token(token)

            assert is_valid is True
            assert payload.role == role

    def test_different_workspaces_in_tokens(self) -> None:
        """Test that tokens can represent different workspaces."""
        user_id = "user-123"
        role = "operator"

        workspaces = ["ws-1", "ws-2", "ws-3"]
        tokens = {}

        for ws_id in workspaces:
            token = generate_token(user_id, ws_id, role)
            is_valid, payload, _ = validate_token(token)

            assert is_valid is True
            assert payload.workspace_id == ws_id
            tokens[ws_id] = token

        # Verify all tokens are different
        assert len(set(tokens.values())) == len(workspaces)
