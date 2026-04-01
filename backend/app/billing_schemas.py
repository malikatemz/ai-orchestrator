"""Advanced types for billing and auth"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum


class SubscriptionPlan(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class CheckoutSessionRequest(BaseModel):
    plan: SubscriptionPlan
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    session_id: str
    url: Optional[str] = None
    client_secret: Optional[str] = None


class UsageResponse(BaseModel):
    tasks_used: int
    tasks_limit: int
    percentage_used: float
    billing_period_start: str
    billing_period_end: str
    renewal_date: str
    plan: str
    plan_name: str
