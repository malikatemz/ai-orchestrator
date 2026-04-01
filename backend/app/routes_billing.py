"""FastAPI routes for Stripe billing"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json

from ..database import get_db
from ..auth import require_permission
from ..billing import (
    create_checkout_session,
    handle_checkout_completed,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    get_usage_for_period,
    check_subscription_active,
)
from ..models import Organization, UserRole
from ..schemas import CheckoutSessionRequest, CheckoutSessionResponse, UsageResponse
from .api_auth import get_current_user

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def checkout(
    request: CheckoutSessionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create Stripe checkout session"""
    
    # Check permission
    if current_user.get("role") not in ["owner", "billing_admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    org_id = current_user.get("org_id")
    
    session = create_checkout_session(
        org_id=org_id,
        plan=request.plan,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )
    
    return CheckoutSessionResponse(**session)


@router.get("/usage", response_model=UsageResponse)
async def usage(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current usage for billing period"""
    
    org_id = current_user.get("org_id")
    usage = get_usage_for_period(db, org_id, days=30)
    
    return UsageResponse(**usage)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Stripe webhooks"""
    
    payload = await request.json()
    event_type = payload.get("type")
    
    try:
        if event_type == "checkout.session.completed":
            handle_checkout_completed(db, payload)
        
        elif event_type == "invoice.payment_failed":
            handle_invoice_payment_failed(db, payload)
        
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(db, payload)
    
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400
    
    return {"status": "success"}
