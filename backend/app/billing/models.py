"""Billing domain models"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class SubscriptionPlan(str, Enum):
    """Subscription plan tiers"""
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class PlanInfo:
    """Pricing and limits for each plan tier"""
    plan: SubscriptionPlan
    price_monthly: float
    task_limit_monthly: int
    stripe_price_id: str
    description: str


# Plan configurations
PLAN_CONFIGS = {
    SubscriptionPlan.STARTER: PlanInfo(
        plan=SubscriptionPlan.STARTER,
        price_monthly=29.00,
        task_limit_monthly=1000,
        stripe_price_id="price_1A2B3C4D5E6F7G8H",  # Placeholder
        description="1,000 tasks/month",
    ),
    SubscriptionPlan.PRO: PlanInfo(
        plan=SubscriptionPlan.PRO,
        price_monthly=99.00,
        task_limit_monthly=10000,
        stripe_price_id="price_2B3C4D5E6F7G8H9I",  # Placeholder
        description="10,000 tasks/month",
    ),
    SubscriptionPlan.ENTERPRISE: PlanInfo(
        plan=SubscriptionPlan.ENTERPRISE,
        price_monthly=0.0,  # Custom pricing
        task_limit_monthly=999999,
        stripe_price_id="",
        description="Custom - Contact sales",
    ),
}


def get_plan_info(plan: SubscriptionPlan) -> PlanInfo:
    """Get plan configuration"""
    return PLAN_CONFIGS.get(plan, PLAN_CONFIGS[SubscriptionPlan.STARTER])
