"""Stripe integration and billing service"""

import stripe
import logging
from datetime import timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config import get_settings
from ..models import Organization, UsageRecord
from ..time_utils import utc_now
from .models import SubscriptionPlan, get_plan_info

logger = logging.getLogger(__name__)

# Initialize Stripe
settings = get_settings()
if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


class BillingError(Exception):
    """Billing operation failed"""
    pass


# ============ Checkout Session ============

def create_checkout_session(
    org_id: str,
    plan: SubscriptionPlan,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """
    Create Stripe Checkout Session for subscription.
    
    Returns:
      {
        "session_id": "cs_1A2B3C...",
        "url": "https://checkout.stripe.com/pay/cs_1A2B3C...",
        "client_secret": "...",
      }
    """
    if not stripe.api_key:
        raise BillingError("Stripe not configured: STRIPE_SECRET_KEY missing")
    
    plan_info = get_plan_info(plan)
    
    if plan == SubscriptionPlan.ENTERPRISE:
        raise BillingError("Enterprise plan requires contacting sales. Use support@orchestrator.ai")
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price": plan_info.stripe_price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"org_id": str(org_id)},
        )
        
        return {
            "session_id": session.id,
            "url": session.url,
            "client_secret": session.client_secret,
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout failed: {str(e)}")
        raise BillingError(f"Checkout creation failed: {str(e)}") from e


# ============ Webhook Handlers ============

def handle_checkout_completed(
    db: Session,
    event: Dict[str, Any],
) -> None:
    """
    Handle checkout.session.completed webhook.
    
    Set org.subscription_status = 'active'
    Store org.stripe_customer_id
    """
    session = event["data"]["object"]
    org_id = session.get("metadata", {}).get("org_id")
    
    if not org_id:
        logger.warning("checkout.session.completed missing org_id")
        return
    
    try:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            logger.error(f"Organization not found: {org_id}")
            return
        
        org.stripe_customer_id = session.get("customer")
        org.subscription_status = "active"
        db.commit()
        logger.info(f"Checkout completed for org: {org_id}")
    
    except Exception as e:
        logger.error(f"Error handling checkout completed: {str(e)}")
        raise


def handle_invoice_payment_failed(
    db: Session,
    event: Dict[str, Any],
) -> None:
    """
    Handle invoice.payment_failed webhook.
    
    Set user.subscription_status = 'past_due'
    """
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    
    if not customer_id:
        logger.warning("invoice.payment_failed missing customer_id")
        return
    
    try:
        org = db.query(Organization).filter(
            Organization.stripe_customer_id == customer_id
        ).first()
        
        if not org:
            logger.error(f"Organization not found for customer: {customer_id}")
            return
        
        org.subscription_status = "past_due"
        db.commit()
        logger.warning(f"Payment failed for org: {org.id}")
    
    except Exception as e:
        logger.error(f"Error handling payment failed: {str(e)}")
        raise


def handle_subscription_deleted(
    db: Session,
    event: Dict[str, Any],
) -> None:
    """
    Handle customer.subscription.deleted webhook.
    
    Set org.subscription_status = 'cancelled'
    """
    subscription = event["data"]["object"]
    customer_id = subscription.get("customer")
    
    if not customer_id:
        logger.warning("customer.subscription.deleted missing customer_id")
        return
    
    try:
        org = db.query(Organization).filter(
            Organization.stripe_customer_id == customer_id
        ).first()
        
        if not org:
            logger.error(f"Organization not found for customer: {customer_id}")
            return
        
        org.subscription_status = "cancelled"
        db.commit()
        logger.info(f"Subscription cancelled for org: {org.id}")
    
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {str(e)}")
        raise


# ============ Usage Reporting ============

def report_usage(
    db: Session,
    org_id: str,
    stripe_subscription_item_id: str,
    quantity: int = 1,
) -> Optional[str]:
    """
    Report usage for billing period.
    
    Calls Stripe's usage reporting API.
    Quantity typically = 1 (one task completed).
    
    Returns usage record ID if successful, None if Stripe disabled.
    """
    if not stripe.api_key:
        logger.debug("Stripe disabled, skipping usage reporting")
        return None
    
    try:
        record = stripe.subscriptionItems.createUsageRecord(
            stripe_subscription_item_id,
            quantity=quantity,
            timestamp=int(utc_now().timestamp()),
        )
        logger.debug(f"Reported usage for org {org_id}: {quantity} tasks")
        return record.get("id")
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe usage reporting failed: {str(e)}")
        # Don't raise - usage reporting is best-effort
        return None


# ============ Usage Lookups ============

def get_usage_for_period(
    db: Session,
    org_id: str,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Get task usage for a billing period.
    
    Returns:
      {
        "tasks_used": 145,
        "tasks_limit": 1000,
        "percentage_used": 14.5,
        "billing_period_start": datetime,
        "billing_period_end": datetime,
        "renewal_date": datetime,
      }
    """
    cutoff = utc_now() - timedelta(days=days)
    
    # Count completed tasks in period
    tasks_used = db.query(func.count(UsageRecord.id)).filter(
        UsageRecord.org_id == org_id,
        UsageRecord.created_at >= cutoff,
    ).scalar() or 0
    
    # Get org plan
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise BillingError(f"Organization not found: {org_id}")
    
    plan = SubscriptionPlan(org.subscription_plan) if org.subscription_plan else SubscriptionPlan.STARTER
    plan_info = get_plan_info(plan)
    
    billing_period_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    billing_period_end = (billing_period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    renewal_date = billing_period_end + timedelta(seconds=1)
    
    return {
        "tasks_used": tasks_used,
        "tasks_limit": plan_info.task_limit_monthly,
        "percentage_used": (tasks_used / plan_info.task_limit_monthly * 100) if plan_info.task_limit_monthly > 0 else 0,
        "billing_period_start": billing_period_start,
        "billing_period_end": billing_period_end,
        "renewal_date": renewal_date,
        "plan": plan.value,
        "plan_name": plan_info.description,
    }


def check_subscription_active(
    db: Session,
    org_id: str,
) -> bool:
    """
    Check if organization has active subscription.
    
    Returns True if subscription_status in ['active', 'trialing']
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return False
    
    return org.subscription_status in ["active", "trialing"]


def enforce_rate_limit(
    db: Session,
    org_id: str,
    allow_if_no_subscription: bool = False,
) -> None:
    """
    Enforce task quotas based on subscription.
    
    Raises BillingError if limit exceeded.
    """
    if not check_subscription_active(db, org_id):
        if allow_if_no_subscription:
            logger.warning(f"Org {org_id} has no active subscription but proceeding (allow_if_no_subscription=True)")
            return
        raise BillingError("Subscription required. Status must be 'active' or 'trialing'.")
    
    usage = get_usage_for_period(db, org_id, days=30)
    
    if usage["tasks_used"] >= usage["tasks_limit"]:
        raise BillingError(
            f"Task limit exceeded for billing period. "
            f"Used {usage['tasks_used']} of {usage['tasks_limit']} tasks. "
            f"Renews on {usage['renewal_date'].isoformat()}"
        )
