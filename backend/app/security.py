"""
Security Middleware - Adds HTTP security headers and enforces security policies
Phase 5: Security Hardening
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

from .config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        settings = get_settings()
        
        # HSTS (HTTP Strict Transport Security)
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = f"max-age={settings.hsts_max_age}; includeSubDomains"
        
        # X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = settings.x_frame_options
        
        # X-Content-Type-Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = settings.x_content_type_options
        
        # X-XSS-Protection - Browser XSS filter
        response.headers["X-XSS-Protection"] = settings.x_xss_protection
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests; "
            "block-all-mixed-content"
        )
        
        # Referrer-Policy - Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        # Remove X-Powered-By header
        response.headers.pop("X-Powered-By", None)
        
        return response


def configure_security(app: FastAPI, settings) -> None:
    """Configure all security settings for the application."""
    
    # Add trusted host middleware
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_origins_list if settings.allowed_origins != "*" else ["*"],
        )
    
    # Add CORS middleware
    if settings.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins_list,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
            max_age=86400,  # 24 hours
        )
    
    # Add security headers middleware
    if settings.enable_security_headers:
        app.add_middleware(SecurityHeadersMiddleware)


__all__ = ["configure_security", "SecurityHeadersMiddleware"]
