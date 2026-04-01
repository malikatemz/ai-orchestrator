"""FastAPI routes for OAuth and auth"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import logging

from ..database import get_db
from ..auth.oauth import google_redirect_url, google_callback, github_redirect_url, github_callback, get_saml_metadata
from ..auth.tokens import create_access_token, create_refresh_token, refresh_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ============ Google OAuth ============

@router.get("/google")
async def google_login():
    """Redirect to Google OAuth"""
    try:
        url, state = google_redirect_url()
        # In production, store state in Redis with TTL for CSRF protection
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Google OAuth error: {str(e)}")
        raise HTTPException(status_code=500, detail="OAuth configuration error")


@router.get("/google/callback")
async def google_callback_handler(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback"""
    try:
        user = await google_callback(db, code, state)
        
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        
        # Redirect to frontend with tokens in query (or use secure cookie)
        return RedirectResponse(
            url=f"http://localhost:3000/auth/success?access_token={access_token}&refresh_token={refresh_token}"
        )
    except Exception as e:
        logger.error(f"Google callback error: {str(e)}")
        raise HTTPException(status_code=400, detail="Authentication failed")


# ============ GitHub OAuth ============

@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth"""
    try:
        url, state = github_redirect_url()
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"GitHub OAuth error: {str(e)}")
        raise HTTPException(status_code=500, detail="OAuth configuration error")


@router.get("/github/callback")
async def github_callback_handler(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """Handle GitHub OAuth callback"""
    try:
        user = await github_callback(db, code, state)
        
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        
        return RedirectResponse(
            url=f"http://localhost:3000/auth/success?access_token={access_token}&refresh_token={refresh_token}"
        )
    except Exception as e:
        logger.error(f"GitHub callback error: {str(e)}")
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
    from ..auth.tokens import revoke_token
    
    try:
        revoke_token(refresh_token, token_type="refresh")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")
