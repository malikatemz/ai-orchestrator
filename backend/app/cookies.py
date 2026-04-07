"""
Secure Cookie Management - OWASP Standards
Enforces secure cookie settings with HTTPOnly, Secure, and SameSite flags
"""

from typing import Optional
from fastapi import Response
from datetime import datetime, timedelta


class SecureCookieManager:
    """Manages secure cookie operations"""
    
    def __init__(self, is_production: bool = False):
        self.is_production = is_production
    
    def set_access_token_cookie(
        self,
        response: Response,
        token: str,
        max_age_seconds: int = 900,  # 15 minutes
    ) -> None:
        """Set secure access token cookie"""
        self._set_cookie(
            response,
            name="access_token",
            value=token,
            max_age=max_age_seconds,
            path="/",
        )
    
    def set_refresh_token_cookie(
        self,
        response: Response,
        token: str,
        max_age_seconds: int = 604800,  # 7 days
    ) -> None:
        """Set secure refresh token cookie"""
        self._set_cookie(
            response,
            name="refresh_token",
            value=token,
            max_age=max_age_seconds,
            path="/auth",  # Only send to auth endpoints
        )
    
    def set_session_cookie(
        self,
        response: Response,
        session_id: str,
        max_age_seconds: int = 3600,  # 1 hour
    ) -> None:
        """Set secure session cookie"""
        self._set_cookie(
            response,
            name="session_id",
            value=session_id,
            max_age=max_age_seconds,
            path="/",
        )
    
    def clear_auth_cookies(self, response: Response) -> None:
        """Clear authentication cookies (logout)"""
        response.delete_cookie(
            "access_token",
            path="/",
            secure=self.is_production,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            "refresh_token",
            path="/auth",
            secure=self.is_production,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            "session_id",
            path="/",
            secure=self.is_production,
            httponly=True,
            samesite="strict",
        )
    
    def _set_cookie(
        self,
        response: Response,
        name: str,
        value: str,
        max_age: int,
        path: str = "/",
    ) -> None:
        """
        Set a secure cookie with all security flags enabled.
        
        Flags:
        - HttpOnly: Prevents JavaScript access (XSS protection)
        - Secure: Only send over HTTPS (in production)
        - SameSite: Prevent CSRF attacks
        - Max-Age: Session timeout
        - Path: Limit cookie scope
        """
        response.set_cookie(
            key=name,
            value=value,
            max_age=max_age,
            expires=datetime.utcnow() + timedelta(seconds=max_age),
            path=path,
            domain=None,  # Current domain only
            secure=self.is_production,  # HTTPS in production, HTTP in dev
            httponly=True,  # Prevent JavaScript access to sensitive cookies
            samesite="strict",  # Prevent CSRF (only send same-site requests)
        )


class CookieValidator:
    """Validates and extracts cookies from requests"""
    
    @staticmethod
    def get_token_from_cookies(cookies: dict, token_name: str = "access_token") -> Optional[str]:
        """
        Safely extract token from cookies.
        
        Prevents cookie-based attacks by validating format.
        """
        token = cookies.get(token_name)
        
        if not token:
            return None
        
        # Validate token format (must be valid JWT or similar)
        if not CookieValidator._is_valid_token_format(token):
            return None
        
        return token
    
    @staticmethod
    def _is_valid_token_format(token: str) -> bool:
        """Validate token format (basic check)"""
        if not token:
            return False
        
        # JWT format: header.payload.signature
        parts = token.split(".")
        return len(parts) == 3 and all(part for part in parts)


__all__ = ["SecureCookieManager", "CookieValidator"]
