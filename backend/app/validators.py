"""
Input Validation Module - OWASP Security Standards
Prevents injection attacks, XSS, path traversal, and other input-based vulnerabilities
"""

import re
from typing import Optional, List
from urllib.parse import urlparse
from fastapi import HTTPException, status


class ValidationError(HTTPException):
    """Custom validation error"""
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InputValidator:
    """Comprehensive input validation following OWASP standards"""
    
    # Constants
    MAX_EMAIL_LENGTH = 254
    MAX_URL_LENGTH = 2048
    MAX_TOKEN_LENGTH = 1024
    MAX_STATE_LENGTH = 128
    MAX_CODE_LENGTH = 256
    MIN_PASSWORD_LENGTH = 12
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    OAUTH_CODE_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
    STATE_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
    TOKEN_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate and sanitize email address"""
        if not email:
            raise ValidationError("Email is required")
        
        if len(email) > InputValidator.MAX_EMAIL_LENGTH:
            raise ValidationError(f"Email exceeds maximum length of {InputValidator.MAX_EMAIL_LENGTH}")
        
        email = email.strip().lower()
        
        if not InputValidator.EMAIL_PATTERN.match(email):
            raise ValidationError("Invalid email format")
        
        return email
    
    @staticmethod
    def validate_oauth_code(code: str) -> str:
        """Validate OAuth authorization code"""
        if not code:
            raise ValidationError("Authorization code is required")
        
        if len(code) > InputValidator.MAX_CODE_LENGTH:
            raise ValidationError(f"Code exceeds maximum length of {InputValidator.MAX_CODE_LENGTH}")
        
        code = code.strip()
        
        # OAuth codes must be alphanumeric with limited special chars
        if not InputValidator.OAUTH_CODE_PATTERN.match(code):
            raise ValidationError("Invalid authorization code format")
        
        return code
    
    @staticmethod
    def validate_state(state: str) -> str:
        """Validate OAuth state parameter (CSRF token)"""
        if not state:
            raise ValidationError("State parameter is required")
        
        if len(state) > InputValidator.MAX_STATE_LENGTH:
            raise ValidationError(f"State exceeds maximum length of {InputValidator.MAX_STATE_LENGTH}")
        
        state = state.strip()
        
        if not InputValidator.STATE_PATTERN.match(state):
            raise ValidationError("Invalid state parameter format")
        
        return state
    
    @staticmethod
    def validate_redirect_url(url: str, allowed_origins: List[str]) -> str:
        """Validate redirect URL against whitelist (prevent open redirect)"""
        if not url:
            raise ValidationError("Redirect URL is required")
        
        if len(url) > InputValidator.MAX_URL_LENGTH:
            raise ValidationError(f"URL exceeds maximum length of {InputValidator.MAX_URL_LENGTH}")
        
        url = url.strip()
        
        # Must be HTTPS
        if not url.startswith("https://") and not url.startswith("http://localhost"):
            raise ValidationError("Redirect URLs must use HTTPS (except localhost)")
        
        # Parse URL and check against whitelist
        try:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            
            if allowed_origins != ["*"] and origin not in allowed_origins:
                raise ValidationError("Redirect URL origin not whitelisted")
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {str(e)}")
        
        return url
    
    @staticmethod
    def validate_token(token: str) -> str:
        """Validate JWT token format"""
        if not token:
            raise ValidationError("Token is required")
        
        if len(token) > InputValidator.MAX_TOKEN_LENGTH:
            raise ValidationError(f"Token exceeds maximum length of {InputValidator.MAX_TOKEN_LENGTH}")
        
        token = token.strip()
        
        # JWT format: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            raise ValidationError("Invalid token format")
        
        # Each part must be base64url encoded
        if not all(InputValidator.TOKEN_PATTERN.match(part) for part in parts):
            raise ValidationError("Invalid token characters")
        
        return token
    
    @staticmethod
    def validate_password(password: str) -> str:
        """Validate password strength"""
        if not password:
            raise ValidationError("Password is required")
        
        if len(password) < InputValidator.MIN_PASSWORD_LENGTH:
            raise ValidationError(f"Password must be at least {InputValidator.MIN_PASSWORD_LENGTH} characters")
        
        # Check for uppercase, lowercase, numbers, and special chars
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValidationError(
                "Password must contain uppercase, lowercase, digits, and special characters"
            )
        
        return password
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Remove potentially dangerous characters"""
        if not value:
            return ""
        
        if len(value) > max_length:
            raise ValidationError(f"Input exceeds maximum length of {max_length}")
        
        # Remove null bytes
        value = value.replace("\0", "")
        
        # Remove excessive whitespace
        value = " ".join(value.split())
        
        return value
    
    @staticmethod
    def validate_no_injection(value: str) -> str:
        """Check for common injection patterns"""
        if not value:
            return value
        
        # SQL injection patterns
        sql_keywords = ["union", "select", "insert", "update", "delete", "drop", "create", "alter"]
        if any(f" {keyword} " in value.lower() for keyword in sql_keywords):
            raise ValidationError("Potentially dangerous input detected")
        
        # Script injection
        if "<script" in value.lower() or "javascript:" in value.lower():
            raise ValidationError("Potentially dangerous input detected")
        
        # Command injection
        if any(char in value for char in ["|", "&", ";", "`", "$"]):
            raise ValidationError("Potentially dangerous input detected")
        
        return value


__all__ = ["InputValidator", "ValidationError"]
