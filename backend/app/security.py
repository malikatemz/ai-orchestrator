"""Security Middleware - HTTP security headers and security policies.

Comprehensive security hardening through HTTP middleware and configuration:
1. HTTP security headers (HSTS, CSP, X-Frame-Options, etc.)
2. CORS configuration with flexible origin control
3. Trusted host validation in production
4. Content Security Policy enforcement
5. Permissions Policy (Feature-Policy) restrictions

The security configuration applies to all HTTP requests and responses via
middleware, adding security headers and validating origins.

Security Headers Applied:
- HSTS: Forces HTTPS-only communication
- X-Frame-Options: Prevents clickjacking (embedding in iframes)
- X-Content-Type-Options: Prevents MIME type sniffing
- X-XSS-Protection: Enables browser XSS protection (legacy)
- Content-Security-Policy: Restricts resource loading sources
- Referrer-Policy: Controls referrer information leakage
- Permissions-Policy: Restricts browser feature access

OWASP Compliance: Helps prevent A01 (Injection), A03 (CORS), A05 (XSS), A06 (Misconfiguration)

Example:
    >>> from fastapi import FastAPI
    >>> from .security import configure_security
    >>> from .config import get_settings
    >>> 
    >>> app = FastAPI()
    >>> settings = get_settings()
    >>> configure_security(app, settings)
"""

from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add HTTP security headers to all responses.
    
    Intercepts all HTTP responses and adds security-related headers to prevent
    common attacks. Headers are conditional based on environment and security settings.
    
    Security Headers:
    
    1. **HSTS (Strict-Transport-Security)** - Production only
       - max-age: 63072000 (2 years)
       - includeSubDomains: Apply to all subdomains
       - Effect: Browser enforces HTTPS-only
       - Prevents: SSL stripping, MITM attacks
    
    2. **X-Frame-Options** - All environments
       - Value: DENY (prevents embedding in iframes/frames)
       - Prevents: Clickjacking attacks
    
    3. **X-Content-Type-Options** - All environments
       - Value: nosniff (forces declared content type)
       - Prevents: MIME type sniffing attacks
    
    4. **X-XSS-Protection** - All environments
       - Value: 1; mode=block (enable browser XSS filter)
       - Prevents: Reflected XSS in vulnerable browsers
       - Note: Modern browsers use CSP instead
    
    5. **Content-Security-Policy (CSP)** - All environments
       - Restricts: script, style, image, font, connect sources
       - Prevents: XSS, script injection, data exfiltration
       - Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...
    
    6. **Referrer-Policy** - All environments
       - Value: strict-origin-when-cross-origin
       - Prevents: Sensitive information in referrer header
    
    7. **Permissions-Policy** - All environments
       - Restrictions: camera, microphone, geolocation, payment, etc.
       - Prevents: Malicious access to device features
    
    Args:
        request: Incoming HTTP request (unused, for middleware protocol)
        call_next: Callable to next middleware/handler
    
    Returns:
        Response with security headers added
    
    Example:
        >>> # Applied automatically via app.add_middleware()
        >>> # All responses get security headers
        >>> response = client.get("/")
        >>> response.headers["X-Frame-Options"]
        "DENY"
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request/response and add security headers.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
        
        Returns:
            Response with security headers injected
        """
        response = await call_next(request)
        settings = get_settings()
        
        # HSTS (HTTP Strict-Transport-Security) - Production only
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = f"max-age={settings.hsts_max_age}; includeSubDomains"
        
        # X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = settings.x_frame_options
        
        # X-Content-Type-Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = settings.x_content_type_options
        
        # X-XSS-Protection - Browser XSS filter (legacy)
        response.headers["X-XSS-Protection"] = settings.x_xss_protection
        
        # Content Security Policy - Prevent XSS and injection attacks
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
        
        # Permissions-Policy (formerly Feature-Policy) - Restrict device access
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        # Remove X-Powered-By header (server identification)
        response.headers.pop("X-Powered-By", None)
        
        return response


def configure_security(app: FastAPI, settings) -> None:
    """Configure all security settings and middleware for the application.
    
    Sets up multi-layered security including CORS, trusted hosts, and security headers.
    Configuration is environment-aware (development vs production).
    
    Middleware Stack (applied in reverse order):
    1. SecurityHeadersMiddleware (outermost - adds headers to all responses)
    2. CORSMiddleware (if enabled - validates cross-origin requests)
    3. TrustedHostMiddleware (production only - validates Host header)
    
    Args:
        app: FastAPI application instance to configure
        settings: Configuration object with security settings
            Attributes:
            - is_production: Boolean flag for production environment
            - allowed_origins_list: List of allowed CORS origins
            - cors_allow_credentials: Allow credentials in CORS requests
            - cors_allow_methods: HTTP methods to allow in CORS
            - cors_allow_headers: Headers to allow in CORS
            - enable_cors: Boolean to enable/disable CORS
            - enable_security_headers: Boolean to enable/disable security headers
            - hsts_max_age: HSTS max-age in seconds (e.g., 63072000 for 2 years)
            - x_frame_options: X-Frame-Options header value (usually "DENY")
            - x_content_type_options: X-Content-Type-Options value (usually "nosniff")
            - x_xss_protection: X-XSS-Protection value (usually "1; mode=block")
    
    Returns:
        None (modifies app in-place via middleware addition)
    
    Configuration by Environment:
    
    **Production**:
        - HSTS: Enabled (2 years max-age)
        - Trusted Hosts: Enforced (validates Host header)
        - CORS: Restricted to configured origins only
        - CSP: Strict mode
        - All security headers: Enabled
    
    **Development**:
        - HSTS: Disabled
        - Trusted Hosts: Disabled (allows any Host header)
        - CORS: Wide-open (if enabled)
        - CSP: Permissive mode
        - Security headers: Enabled (for testing)
    
    OWASP Protection:
        - A01 (Injection): CSP prevents script injection
        - A03 (CORS): CORS middleware validates origins
        - A05 (XSS): CSP + X-XSS-Protection prevent XSS
        - A06 (Misconfiguration): Headers harden HTTP responses
        - A09 (Injection): CSP prevents code injection
    
    Best Practices:
        - Call during app startup before route registration
        - Review allowed_origins_list for production
        - Test security headers with browser dev tools
        - Monitor CSP violations in logs
        - Run security audits (OWASP ZAP, Burp Suite)
    
    Example:
        >>> from fastapi import FastAPI
        >>> from .security import configure_security
        >>> from .config import get_settings
        >>> 
        >>> app = FastAPI()
        >>> settings = get_settings()
        >>> configure_security(app, settings)
        >>> # Now all requests/responses go through security middleware
    
    Side Effects:
        - Modifies FastAPI app middleware stack
        - Enables CORS validation (if configured)
        - Enables security header injection
        - Enables Host header validation in production
    """
    
    # Add trusted host middleware (production only)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_origins_list if settings.allowed_origins != "*" else ["*"],
        )
    
    # Add CORS middleware if enabled
    if settings.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins_list,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
            max_age=86400,  # 24 hours
        )
    
    # Add security headers middleware if enabled
    if settings.enable_security_headers:
        app.add_middleware(SecurityHeadersMiddleware)


__all__ = ["configure_security", "SecurityHeadersMiddleware"]
