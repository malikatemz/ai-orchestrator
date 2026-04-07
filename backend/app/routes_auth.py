"""FastAPI routes for OAuth and auth - SECURITY HARDENED"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import logging
import redis
import secrets
from datetime import timedelta, datetime

from .database import get_db
from .auth.oauth import google_redirect_url, google_callback, github_redirect_url, github_callback, get_saml_metadata
from .auth.tokens import create_access_token, create_refresh_token, refresh_access_token
from .config import get_settings
from .observability import configure_logging

logger = configure_logging()
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


# ============ Google OAuth ============

@router.get("/google")
async def google_login(request_origin: str = Query(...)):
    """
    Initiate Google OAuth flow with CSRF protection.
    SECURITY: Validates origin, stores state in Redis with TTL
    """
    try:
        # Validate request origin
        allowed_origins = settings.allowed_origins_list
        if allowed_origins != ["*"] and request_origin not in allowed_origins:
            logger.warning(f"Invalid origin for OAuth: {request_origin}")
            raise HTTPException(status_code=403, detail="Invalid request origin")
        
        url, state = google_redirect_url()
        
        # Store state in Redis with 10-minute TTL for CSRF validation
        try:
            redis_client = redis.from_url(settings.redis_url)
            state_key = f"oauth_state:google:{state}"
            redis_client.setex(state_key, 600, request_origin)  # 10 minutes
        except Exception as e:
            logger.warning(f"Failed to store OAuth state: {str(e)}")
            # Continue without Redis - state validation disabled
        
        return RedirectResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth error: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="OAuth configuration error")


@router.get("/google/callback")
async def google_callback_handler(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Handle Google OAuth callback with CSRF validation.
    SECURITY: Validates state parameter, uses secure cookies for tokens
    """
    if not code or not state:
        logger.warning("Google callback missing code or state")
        raise HTTPException(status_code=400, detail="Missing authorization code or state")
    
    try:
        # Validate state parameter against Redis cache (CSRF protection)
        try:
            redis_client = redis.from_url(settings.redis_url)
            state_key = f"oauth_state:google:{state}"
            stored_origin = redis_client.get(state_key)
            
            if not stored_origin:
                logger.warning(f"Invalid or expired OAuth state: {state[:10]}...")
                raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
            
            # Delete state (prevent replay attacks)
            redis_client.delete(state_key)
        except redis.ConnectionError:
            logger.warning("Redis connection failed - skipping state validation")
            # In production, this should fail secure
            if settings.is_production:
                raise HTTPException(status_code=500, detail="Service temporarily unavailable")
        
        # Exchange code for user info
        user = await google_callback(db, code, state)
        
        # Create tokens
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        
        # Return tokens via secure HTTPOnly cookies (HTTPS only in production)
        response = JSONResponse(
            content={
                "status": "success",
                "message": "Authentication successful",
                "user": {"email": user.get("email"), "name": user.get("name")},
            },
            status_code=200,
        )
        
        # Set secure cookies
        response.set_cookie(
            "access_token",
            access_token,
            max_age=900,  # 15 minutes
            httponly=True,  # Prevent JavaScript access
            secure=settings.is_production,  # HTTPS only in production
            samesite="strict",  # CSRF protection
            path="/",
        )
        
        response.set_cookie(
            "refresh_token",
            refresh_token,
            max_age=604800,  # 7 days
            httponly=True,
            secure=settings.is_production,
            samesite="strict",
            path="/",
        )
        
        logger.info(f"Successful Google OAuth for user {user.get('email')}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google callback authentication failed: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Authentication failed")


# ============ GitHub OAuth ============

@router.get("/github")
async def github_login(request_origin: str = Query(...)):
    """
    Initiate GitHub OAuth flow with CSRF protection.
    SECURITY: Validates origin, stores state in Redis with TTL
    """
    try:
        # Validate request origin
        allowed_origins = settings.allowed_origins_list
        if allowed_origins != ["*"] and request_origin not in allowed_origins:
            logger.warning(f"Invalid origin for OAuth: {request_origin}")
            raise HTTPException(status_code=403, detail="Invalid request origin")
        
        url, state = github_redirect_url()
        
        # Store state in Redis with 10-minute TTL
        try:
            redis_client = redis.from_url(settings.redis_url)
            state_key = f"oauth_state:github:{state}"
            redis_client.setex(state_key, 600, request_origin)
        except Exception as e:
            logger.warning(f"Failed to store OAuth state: {str(e)}")
        
        return RedirectResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub OAuth error: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="OAuth configuration error")


@router.get("/github/callback")
async def github_callback_handler(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Handle GitHub OAuth callback with CSRF validation.
    SECURITY: Validates state parameter, uses secure cookies for tokens
    """
    if not code or not state:
        logger.warning("GitHub callback missing code or state")
        raise HTTPException(status_code=400, detail="Missing authorization code or state")
    
    try:
        # Validate state parameter (CSRF protection)
        try:
            redis_client = redis.from_url(settings.redis_url)
            state_key = f"oauth_state:github:{state}"
            stored_origin = redis_client.get(state_key)
            
            if not stored_origin:
                logger.warning(f"Invalid or expired OAuth state: {state[:10]}...")
                raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
            
            # Delete state to prevent replay
            redis_client.delete(state_key)
        except redis.ConnectionError:
            logger.warning("Redis connection failed - skipping state validation")
            if settings.is_production:
                raise HTTPException(status_code=500, detail="Service temporarily unavailable")
        
        # Exchange code for user info
        user = await github_callback(db, code, state)
        
        # Create tokens
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        
        # Return tokens via secure HTTPOnly cookies
        response = JSONResponse(
            content={
                "status": "success",
                "message": "Authentication successful",
                "user": {"login": user.get("login"), "email": user.get("email")},
            },
            status_code=200,
        )
        
        # Set secure cookies
        response.set_cookie(
            "access_token",
            access_token,
            max_age=900,
            httponly=True,
            secure=settings.is_production,
            samesite="strict",
            path="/",
        )
        
        response.set_cookie(
            "refresh_token",
            refresh_token,
            max_age=604800,
            httponly=True,
            secure=settings.is_production,
            samesite="strict",
            path="/",
        )
        
        logger.info(f"Successful GitHub OAuth for user {user.get('login')}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub callback authentication failed: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Authentication failed")


# ============ SAML ============

@router.get("/saml/metadata")
async def saml_metadata():
    """Return SAML 2.0 metadata"""
    metadata = get_saml_metadata()
    return {
        "content": metadata,
        "note": "Replace with actual SAML IdP metadata after configuring python3-saml"
    }


# ============ Token Refresh ============

@router.post("/refresh")
async def refresh_token_endpoint(
    refresh_token: str,
    db: Session = Depends(get_db),
):
    """Exchange refresh token for new access token"""
    try:
        new_access_token = refresh_access_token(refresh_token, db)
        return {"access_token": new_access_token, "token_type": "bearer"}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ============ Logout ============

@router.post("/logout")
async def logout(
    refresh_token: str,
):
    """Revoke refresh token"""
    from .auth.tokens import revoke_token
    
    try:
        revoke_token(refresh_token, token_type="refresh")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")

