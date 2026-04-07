"""OAuth2 providers - Google and GitHub"""

import httpx
import logging
import secrets
import base64
from typing import Dict, Any, Optional
from urllib.parse import urlencode, parse_qs
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import User, Organization, UserRole
import uuid

logger = logging.getLogger(__name__)


class OAuthError(Exception):
    """OAuth operation failed"""
    pass


# ============ Google OAuth ============

class GoogleOAuth:
    """Google OAuth2 flow - SECURITY: Uses configured redirect URIs, HTTPS only"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client_id = self.settings.google_client_id
        self.client_secret = self.settings.google_client_secret
        # SECURITY: Use configured redirect URI from environment
        self.redirect_uri = self.settings.google_redirect_uri
        if self.settings.is_production and not self.redirect_uri.startswith("https://"):
            raise OAuthError("Google redirect URI must use HTTPS in production")
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://www.googleapis.com/oauth2/v4/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Get Google authorization URL.
        
        Returns (auth_url, state_token)
        """
        if not self.client_id or not self.client_secret:
            raise OAuthError("Google OAuth not configured")
        
        state = state or secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
        }
        
        return f"{self.auth_url}?{urlencode(params)}", state
    
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Returns user info dict
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        
        async with httpx.AsyncClient() as client:
            # Get tokens
            resp = await client.post(self.token_url, data=payload)
            resp.raise_for_status()
            token_data = resp.json()
            access_token = token_data["access_token"]
            
            # Get user info
            headers = {"Authorization": f"Bearer {access_token}"}
            resp = await client.get(self.userinfo_url, headers=headers)
            resp.raise_for_status()
            user_info = resp.json()
        
        return {
            "email": user_info["email"],
            "full_name": user_info.get("name", ""),
            "profile_picture": user_info.get("picture"),
            "google_id": user_info["id"],
            "provider": "google",
        }


def google_redirect_url(state: Optional[str] = None) -> tuple[str, str]:
    """Get Google OAuth redirect URL"""
    oauth = GoogleOAuth()
    return oauth.get_authorization_url(state)


async def google_callback(
    db: Session,
    code: str,
    state: Optional[str] = None,
) -> User:
    """
    Handle Google OAuth callback.
    
    Upserts user and returns or creates org.
    """
    oauth = GoogleOAuth()
    
    try:
        user_info = await oauth.exchange_code(code)
    except Exception as e:
        logger.error(f"Google OAuth exchange failed: {str(e)}")
        raise OAuthError(f"Google authentication failed: {str(e)}") from e
    
    email = user_info["email"]
    google_id = user_info["google_id"]
    
    # Upsert user
    user = db.query(User).filter(User.google_id == google_id).first()
    
    if not user:
        user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Create new user + org
        org = Organization(
            id=uuid.uuid4(),
            name=" ".join(email.split("@")),
            slug=email.split("@")[0],
        )
        db.add(org)
        db.flush()
        
        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=user_info.get("full_name", ""),
            profile_picture=user_info.get("profile_picture"),
            google_id=google_id,
            org_id=org.id,
            role=UserRole.OWNER,
            subscription_status="trialing",
        )
        db.add(user)
    else:
        # Update existing user
        user.full_name = user_info.get("full_name", user.full_name)
        user.profile_picture = user_info.get("profile_picture", user.profile_picture)
        user.google_id = google_id
    
    db.commit()
    return user


# ============ GitHub OAuth ============

class GitHubOAuth:
    """GitHub OAuth2 flow - SECURITY: Uses configured redirect URIs, HTTPS only"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client_id = self.settings.github_client_id
        self.client_secret = self.settings.github_client_secret
        # SECURITY: Use configured redirect URI from environment
        self.redirect_uri = self.settings.github_redirect_uri
        if self.settings.is_production and not self.redirect_uri.startswith("https://"):
            raise OAuthError("GitHub redirect URI must use HTTPS in production")
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.userinfo_url = "https://api.github.com/user"
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """Get GitHub authorization URL"""
        if not self.client_id or not self.client_secret:
            raise OAuthError("GitHub OAuth not configured")
        
        state = state or secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        
        return f"{self.auth_url}?{urlencode(params)}", state
    
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        
        headers = {"Accept": "application/json"}
        
        async with httpx.AsyncClient() as client:
            # Get tokens
            resp = await client.post(
                self.token_url,
                data=payload,
                headers=headers,
            )
            resp.raise_for_status()
            token_data = resp.json()
            access_token = token_data["access_token"]
            
            # Get user info
            headers["Authorization"] = f"Bearer {access_token}"
            resp = await client.get(self.userinfo_url, headers=headers)
            resp.raise_for_status()
            user_info = resp.json()
        
        return {
            "email": user_info.get("email", f"{user_info['login']}@github.local"),
            "full_name": user_info.get("name", user_info.get("login", "")),
            "profile_picture": user_info.get("avatar_url"),
            "github_id": user_info["id"],
            "provider": "github",
        }


def github_redirect_url(state: Optional[str] = None) -> tuple[str, str]:
    """Get GitHub OAuth redirect URL"""
    oauth = GitHubOAuth()
    return oauth.get_authorization_url(state)


async def github_callback(
    db: Session,
    code: str,
    state: Optional[str] = None,
) -> User:
    """Handle GitHub OAuth callback - same pattern as Google"""
    oauth = GitHubOAuth()
    
    try:
        user_info = await oauth.exchange_code(code)
    except Exception as e:
        logger.error(f"GitHub OAuth exchange failed: {str(e)}")
        raise OAuthError(f"GitHub authentication failed: {str(e)}") from e
    
    email = user_info["email"]
    github_id = user_info["github_id"]
    
    # Upsert user
    user = db.query(User).filter(User.github_id == github_id).first()
    
    if not user:
        user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Create new user + org
        org = Organization(
            id=uuid.uuid4(),
            name=user_info.get("full_name", email.split("@")[0]),
            slug=email.split("@")[0],
        )
        db.add(org)
        db.flush()
        
        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=user_info.get("full_name", ""),
            profile_picture=user_info.get("profile_picture"),
            github_id=github_id,
            org_id=org.id,
            role=UserRole.OWNER,
            subscription_status="trialing",
        )
        db.add(user)
    else:
        # Update existing user
        user.full_name = user_info.get("full_name", user.full_name)
        user.profile_picture = user_info.get("profile_picture", user.profile_picture)
        user.github_id = github_id
    
    db.commit()
    return user


# ============ SAML Metadata ============

def get_saml_metadata() -> str:
    """
    Return placeholder SAML 2.0 metadata.
    
    Swap in actual IdP (Okta, Azure AD, etc.) using pysaml2 or python3-saml.
    """
    settings = get_settings()
    
    # Placeholder - real SAML setup requires:
    # pip install python3-saml
    # Configure IdP metadata and SP settings
    
    metadata_xml = f"""<EntityDescriptor
        xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
        entityID="https://orchestrator.ai/saml/metadata">
        
        <SPSSODescriptor
            AuthnRequestsSigned="false"
            WantAssertionsSigned="true"
            protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
            
            <SingleLogoutService
                Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                Location="https://orchestrator.ai/auth/saml/logout"/>
                
            <AssertionConsumerService
                Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                Location="https://orchestrator.ai/auth/saml/callback"
                index="1"/>
        </SPSSODescriptor>
    </EntityDescriptor>"""
    
    return metadata_xml
