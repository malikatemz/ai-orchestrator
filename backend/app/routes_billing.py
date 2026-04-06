"""FastAPI routes for Stripe billing"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json
import stripe
import logging

from .database import get_db
from .config import get_settings
from .billing import (
    create_checkout_session,
    handle_checkout_completed,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    get_usage_for_period,
    check_subscription_active,
)
from .models import Organization, UsageRecord
from .schemas import CheckoutSessionRequest, CheckoutSessionResponse, UsageResponse
from .api_auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

settings = get_settings()


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
    """
    Handle Stripe webhooks with signature verification.
    
    Webhook signature is verified using Stripe's signing secret.
    Only processes if signature is valid.
    """
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        logger.warning("Stripe webhook missing signature header")
        return {"status": "error", "message": "Missing signature"}, 403
    
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except ValueError as e:
        logger.warning(f"Invalid payload: {str(e)}")
        return {"status": "error", "message": "Invalid payload"}, 400
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f"Invalid signature: {str(e)}")
        return {"status": "error", "message": "Invalid signature"}, 400
    
    event_type = event.get("type")
    
    try:
        if event_type == "checkout.session.completed":
            handle_checkout_completed(db, event)
        
        elif event_type == "invoice.payment_failed":
            handle_invoice_payment_failed(db, event)
        
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(db, event)
        
        else:
            logger.debug(f"Unhandled event type: {event_type}")
    
    except Exception as e:
        logger.error(f"Error handling webhook {event_type}: {str(e)}")
        return {"status": "error", "message": str(e)}, 400
    
    return {"status": "success"}
