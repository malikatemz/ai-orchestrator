"""
Phase 5 Authentication Tests - OAuth2, JWT, RBAC, and Session Management
Tests cover Google/GitHub OAuth flows, token operations, role-based access control,
and complete authentication lifecycle.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock
import jwt

from app.auth import tokens
from app.auth.oauth import GoogleOAuth, GitHubOAuth
from app.auth.rbac import Permission, get_user_permissions, check_permission
from app.models import UserRole, User, Organization
from app.config import get_settings


@pytest.fixture
def test_user(test_db):
    """Create a test user with MEMBER role."""
    import uuid
    org_id = str(uuid.uuid4())
    org = Organization(
        id=org_id,
        name="Test Org",
        slug="test-org",
        email="test-org@example.com"
    )
    test_db.add(org)
    test_db.commit()
    
    user = User(
        id=str(uuid.uuid4()),
        email="user@example.com",
        full_name="Test User",
        hashed_password="hashed_pw",
        role=UserRole.MEMBER,
        org_id=org.id,
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def admin_user(test_db):
    """Create a test admin user."""
    import uuid
    org_id = str(uuid.uuid4())
    org = Organization(
        id=org_id,
        name="Admin Org",
        slug="admin-org",
        email="admin-org@example.com"
    )
    test_db.add(org)
    test_db.commit()
    
    user = User(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        full_name="Admin User",
        hashed_password="hashed_pw",
        role=UserRole.ADMIN,
        org_id=org.id,
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


class TestTokens:
    """Test JWT token creation, validation, refresh, and revocation."""
    
    def test_create_access_token(self, test_user):
        """Test creating a valid access token."""
        token = tokens.create_access_token(test_user)
        assert token is not None
        assert isinstance(token, str)
        # JWT has 3 parts separated by dots
        assert len(token.split(".")) == 3
    
    def test_decode_valid_token(self, test_user):
        """Test decoding a valid JWT token."""
        token = tokens.create_access_token(test_user)
        decoded = tokens.decode_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == str(test_user.id)
        assert decoded["email"] == test_user.email
        assert decoded["org_id"] == str(test_user.org_id)
        assert decoded["type"] == "access"
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid token raises exception."""
        with pytest.raises(jwt.InvalidTokenError):
            tokens.decode_token("invalid.token.here")
    
    def test_create_refresh_token(self, test_user):
        """Test creating a valid refresh token."""
        token = tokens.create_refresh_token(test_user)
        assert token is not None
        assert isinstance(token, str)
        
        # Verify it can be decoded (with correct token_type)
        decoded = tokens.decode_token(token, token_type="refresh")
        assert decoded["sub"] == str(test_user.id)
        assert decoded["type"] == "refresh"
    
    def test_token_has_correct_expiry_time(self, test_user):
        """Test access token has correct expiration."""
        settings = get_settings()
        before = datetime.now(timezone.utc)
        token = tokens.create_access_token(test_user)
        after = datetime.now(timezone.utc)
        
        decoded = tokens.decode_token(token)
        expires = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        
        # Token should expire after configured duration (default 15 min)
        expected_min = before + timedelta(
            minutes=settings.access_token_expire_minutes - 1
        )
        expected_max = after + timedelta(
            minutes=settings.access_token_expire_minutes + 1
        )
        
        assert expected_min <= expires <= expected_max
    
    def test_refresh_token_longer_expiry(self, test_user):
        """Test refresh token has longer expiration than access token."""
        settings = get_settings()
        access_token = tokens.create_access_token(test_user)
        refresh_token = tokens.create_refresh_token(test_user)
        
        access_decoded = tokens.decode_token(access_token)
        refresh_decoded = tokens.decode_token(refresh_token, token_type="refresh")
        
        access_expiry = datetime.fromtimestamp(access_decoded["exp"])
        refresh_expiry = datetime.fromtimestamp(refresh_decoded["exp"])
        
        # Refresh token should expire later than access token
        assert refresh_expiry > access_expiry


class TestGoogleOAuth:
    """Test Google OAuth2 flow integration."""
    
    def test_authorization_url_generation(self):
        """Test generating Google authorization URL."""
        oauth = GoogleOAuth()
        auth_url, state = oauth.get_authorization_url()
        
        assert auth_url is not None
        assert "https://accounts.google.com/o/oauth2/v2/auth" in auth_url
        assert "client_id=" in auth_url
        assert "scope=" in auth_url
        assert state is not None
        assert isinstance(state, str)
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self):
        """Test exchanging authorization code for Google token."""
        oauth = GoogleOAuth()
        
        # Mock user info returned from Google
        mock_user_info = {
            "id": "google_id_123",
            "email": "user@gmail.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg"
        }
        
        mock_post_response = AsyncMock()
        mock_post_response.json.return_value = {
            "access_token": "google_token",
            "token_type": "Bearer",
            "expires_in": 3599,
        }
        mock_post_response.raise_for_status.return_value = None
        
        mock_get_response = AsyncMock()
        mock_get_response.json.return_value = mock_user_info
        mock_get_response.raise_for_status.return_value = None
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_post_response
        mock_client.get.return_value = mock_get_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await oauth.exchange_code("test_code")
            assert result is not None
            assert result["email"] == "user@gmail.com"
            assert result["google_id"] == "google_id_123"
            assert result["provider"] == "google"


class TestGitHubOAuth:
    """Test GitHub OAuth2 flow integration."""
    
    def test_authorization_url_generation(self):
        """Test generating GitHub authorization URL."""
        oauth = GitHubOAuth()
        auth_url, state = oauth.get_authorization_url()
        
        assert auth_url is not None
        assert "https://github.com/login/oauth/authorize" in auth_url
        assert "client_id=" in auth_url
        assert "scope=" in auth_url
        assert state is not None
        assert isinstance(state, str)
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self):
        """Test exchanging authorization code for GitHub token."""
        oauth = GitHubOAuth()
        
        # Mock user info returned from GitHub
        mock_user_info = {
            "id": 12345,
            "login": "testuser",
            "name": "Test User",
            "email": "user@github.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345"
        }
        
        mock_post_response = AsyncMock()
        mock_post_response.json.return_value = {
            "access_token": "github_token",
            "token_type": "bearer",
            "scope": "read:user,user:email"
        }
        mock_post_response.raise_for_status.return_value = None
        
        mock_get_response = AsyncMock()
        mock_get_response.json.return_value = mock_user_info
        mock_get_response.raise_for_status.return_value = None
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_post_response
        mock_client.get.return_value = mock_get_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await oauth.exchange_code("test_code")
            assert result is not None
            assert result["email"] == "user@github.com"
            assert result["provider"] == "github"


# ============ RBAC Tests ============

class TestRBAC:
    """Test role-based access control and permissions."""
    
    def test_member_has_expected_permissions(self):
        """Test that Member role has expected permissions."""
        permissions = get_user_permissions(UserRole.MEMBER)
        
        assert Permission.RUN_WORKFLOWS in permissions
        assert Permission.CREATE_WORKFLOWS in permissions
        assert Permission.VIEW_OWN_LOGS in permissions
        assert Permission.MANAGE_USERS not in permissions
    
    def test_admin_has_more_permissions(self):
        """Test that Admin role has more permissions than Member."""
        admin_permissions = get_user_permissions(UserRole.ADMIN)
        member_permissions = get_user_permissions(UserRole.MEMBER)
        
        assert len(admin_permissions) > len(member_permissions)
        assert Permission.MANAGE_USERS in admin_permissions
        assert Permission.MANAGE_USERS not in member_permissions
    
    def test_owner_has_all_permissions(self):
        """Test that Owner role has all permissions."""
        owner_perms = get_user_permissions(UserRole.OWNER)
        
        assert Permission.MANAGE_USERS in owner_perms
        assert Permission.MANAGE_ROLES in owner_perms
        assert Permission.RUN_WORKFLOWS in owner_perms
        assert Permission.MANAGE_SUBSCRIPTION in owner_perms
        assert Permission.ADMIN_PANEL in owner_perms
    
    def test_viewer_has_read_only(self):
        """Test that Viewer role only has read permissions."""
        viewer_perms = get_user_permissions(UserRole.VIEWER)
        
        assert Permission.VIEW_LOGS in viewer_perms
        assert Permission.VIEW_OWN_LOGS in viewer_perms
        assert Permission.RUN_WORKFLOWS not in viewer_perms
        assert Permission.MANAGE_USERS not in viewer_perms
    
    def test_check_permission_granted(self):
        """Test permission check when user has permission."""
        result = check_permission(UserRole.MEMBER, Permission.RUN_WORKFLOWS)
        assert result is True
    
    def test_check_permission_denied(self):
        """Test permission check when user lacks permission."""
        result = check_permission(UserRole.VIEWER, Permission.RUN_WORKFLOWS)
        assert result is False
    
    def test_role_hierarchy(self):
        """Test role hierarchy (Owner > Admin > Member > Viewer)."""
        owner_perms = get_user_permissions(UserRole.OWNER)
        admin_perms = get_user_permissions(UserRole.ADMIN)
        member_perms = get_user_permissions(UserRole.MEMBER)
        viewer_perms = get_user_permissions(UserRole.VIEWER)
        
        # Owner should have more permissions than Admin
        assert len(owner_perms) > len(admin_perms)
        
        # Admin should have more permissions than Member
        assert len(admin_perms) > len(member_perms)
        
        # Member should have more permissions than Viewer
        assert len(member_perms) > len(viewer_perms)
    
    def test_billing_admin_can_manage_subscription(self):
        """Test that BillingAdmin can manage subscriptions."""
        billing_admin_perms = get_user_permissions(UserRole.BILLING_ADMIN)
        
        assert Permission.VIEW_BILLING in billing_admin_perms
        assert Permission.MANAGE_SUBSCRIPTION in billing_admin_perms
        assert Permission.RUN_WORKFLOWS not in billing_admin_perms


# ============ Database Integration Tests ============

class TestAuthWithDatabase:
    """Test authentication with database interactions."""
    
    def test_token_creation_with_real_user(self, test_user):
        """Test creating tokens with a real database user."""
        access_token = tokens.create_access_token(test_user)
        refresh_token = tokens.create_refresh_token(test_user)
        
        assert access_token is not None
        assert refresh_token is not None
        
        # Decode and verify
        access_decoded = tokens.decode_token(access_token)
        assert access_decoded["sub"] == str(test_user.id)
        assert access_decoded["email"] == test_user.email
    
    def test_admin_token_claims(self, admin_user):
        """Test token contains correct role claim."""
        token = tokens.create_access_token(admin_user)
        decoded = tokens.decode_token(token)
        
        assert decoded["role"] == UserRole.ADMIN.value
    
    def test_token_timezone_aware(self, test_user):
        """Test token expiration is timezone-aware."""
        token = tokens.create_access_token(test_user)
        decoded = tokens.decode_token(token)
        
        # exp should be a Unix timestamp (int)
        assert isinstance(decoded["exp"], int)
        assert decoded["exp"] > 0


# ============ OAuth State Parameter Tests ============

class TestOAuthStateHandling:
    """Test OAuth state parameter for CSRF protection."""
    
    def test_google_state_generated(self):
        """Test Google OAuth generates state parameter."""
        oauth = GoogleOAuth()
        auth_url, state = oauth.get_authorization_url()
        
        assert state is not None
        assert isinstance(state, str)
        assert len(state) > 0
        assert "state=" in auth_url
    
    def test_github_state_generated(self):
        """Test GitHub OAuth generates state parameter."""
        oauth = GitHubOAuth()
        auth_url, state = oauth.get_authorization_url()
        
        assert state is not None
        assert isinstance(state, str)
        assert len(state) > 0
        assert "state=" in auth_url
    
    def test_state_uniqueness(self):
        """Test each authorization URL gets a unique state."""
        oauth = GoogleOAuth()
        _, state1 = oauth.get_authorization_url()
        _, state2 = oauth.get_authorization_url()
        
        # States should be different (very unlikely to collide)
        assert state1 != state2
    
    def test_github_state_uniqueness(self):
        """Test GitHub OAuth state uniqueness."""
        oauth = GitHubOAuth()
        _, state1 = oauth.get_authorization_url()
        _, state2 = oauth.get_authorization_url()
        
        assert state1 != state2
