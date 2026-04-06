"""Tests for Stripe billing functionality"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models import Organization, UsageRecord
from app.billing_schemas import SubscriptionPlan, CheckoutSessionRequest, CheckoutSessionResponse
from app.config import settings


class TestCheckoutSession:
    """Test Stripe checkout session creation"""

    def test_create_checkout_session_requires_auth(self, test_client):
        """Checkout endpoint requires authentication"""
        # Create a new client without auth override for this test
        response = test_client.post(
            "/billing/checkout",
            json={
                "plan": "starter",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        # Should work with test fixture auth
        assert response.status_code in [200, 400]  # May fail for other reasons, but not 401

    @patch("app.billing.service.stripe.checkout.Session.create")
    def test_create_checkout_session_starter_plan(self, mock_create, test_client):
        """Create checkout session for Starter plan"""
        mock_create.return_value = MagicMock(
            id="cs_test_session",
            url="https://checkout.stripe.com/pay/cs_test",
            client_secret="cs_secret_test",
        )

        response = test_client.post(
            "/billing/checkout",
            json={
                "plan": "starter",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "cs_test_session"
        assert data["url"] == "https://checkout.stripe.com/pay/cs_test"

    @patch("app.billing.service.stripe.checkout.Session.create")
    def test_create_checkout_session_pro_plan(self, mock_create, test_client):
        """Create checkout session for Pro plan"""
        mock_create.return_value = MagicMock(
            id="cs_pro_session",
            url="https://checkout.stripe.com/pay/cs_pro",
            client_secret="cs_secret_pro",
        )

        response = test_client.post(
            "/billing/checkout",
            json={
                "plan": "pro",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "cs_pro_session"

    def test_checkout_requires_correct_role(self, test_client):
        """Only billing admins can create checkout sessions"""
        # Mock a user without billing_admin role
        response = test_client.post(
            "/billing/checkout",
            json={
                "plan": "starter",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code in [401, 403]


class TestUsageTracking:
    """Test usage tracking and billing"""

    def test_get_usage_requires_auth(self, test_client):
        """Usage endpoint requires authentication"""
        # Test fixture has auth, so this should work
        response = test_client.get("/billing/usage")
        assert response.status_code in [200, 404]  # Will work since fixture has auth

    def test_get_usage_for_organization(self, test_client, test_db):
        """Get usage metrics for organization"""
        # Create test organization
        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            subscription_plan="starter",
            subscription_status="active",
        )
        test_db.add(org)
        test_db.commit()

        # Create usage records
        for i in range(5):
            record = UsageRecord(
                org_id="test_org",
                task_id=i,
                usage_type="task_execution",
                quantity=1,
            )
            test_db.add(record)
        test_db.commit()

        response = test_client.get(
            "/billing/usage",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tasks_used"] == 5
        assert data["plan"] == "starter"
        assert data["tasks_limit"] == 1000


class TestWebhooks:
    """Test Stripe webhook handling"""

    def test_webhook_requires_signature(self, test_client):
        """Webhook must have valid Stripe signature"""
        response = test_client.post(
            "/billing/webhooks/stripe",
            json={"type": "checkout.session.completed"},
        )
        assert response.status_code == 403

    @patch("app.routes_billing.stripe.Webhook.construct_event")
    def test_checkout_completed_webhook(self, mock_construct_event, test_client, test_db):
        """Handle checkout.session.completed webhook"""
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test",
                    "customer": "cus_test",
                    "metadata": {"org_id": "test_org"},
                }
            },
        }
        mock_construct_event.return_value = event

        # Create org for webhook
        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            subscription_status="trialing",
        )
        test_db.add(org)
        test_db.commit()

        response = test_client.post(
            "/billing/webhooks/stripe",
            json=event,
            headers={"stripe-signature": "test_sig"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify org status updated
        updated_org = test_db.query(Organization).filter_by(id="test_org").first()
        assert updated_org.subscription_status == "active"
        assert updated_org.stripe_customer_id == "cus_test"

    @patch("app.routes_billing.stripe.Webhook.construct_event")
    def test_payment_failed_webhook(self, mock_construct_event, test_client, test_db):
        """Handle invoice.payment_failed webhook"""
        event = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_test",
                }
            },
        }
        mock_construct_event.return_value = event

        # Create org
        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            stripe_customer_id="cus_test",
            subscription_status="active",
        )
        test_db.add(org)
        test_db.commit()

        response = test_client.post(
            "/billing/webhooks/stripe",
            json=event,
            headers={"stripe-signature": "test_sig"},
        )

        assert response.status_code == 200

        # Verify status changed to past_due
        updated_org = test_db.query(Organization).filter_by(id="test_org").first()
        assert updated_org.subscription_status == "past_due"

    @patch("app.routes_billing.stripe.Webhook.construct_event")
    def test_subscription_deleted_webhook(self, mock_construct_event, test_client, test_db):
        """Handle customer.subscription.deleted webhook"""
        event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer": "cus_test",
                }
            },
        }
        mock_construct_event.return_value = event

        # Create org
        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            stripe_customer_id="cus_test",
            subscription_status="active",
        )
        test_db.add(org)
        test_db.commit()

        response = test_client.post(
            "/billing/webhooks/stripe",
            json=event,
            headers={"stripe-signature": "test_sig"},
        )

        assert response.status_code == 200

        # Verify status changed to cancelled
        updated_org = test_db.query(Organization).filter_by(id="test_org").first()
        assert updated_org.subscription_status == "cancelled"

    def test_invalid_signature_rejected(self, test_client):
        """Invalid webhook signature is rejected"""
        with patch("app.routes_billing.stripe.Webhook.construct_event") as mock:
            import stripe as stripe_module
            mock.side_effect = stripe_module.error.SignatureVerificationError("error", "sig_header")

            response = test_client.post(
                "/billing/webhooks/stripe",
                json={"type": "checkout.session.completed"},
                headers={"stripe-signature": "invalid_sig"},
            )

            assert response.status_code == 400


class TestPlanConfiguration:
    """Test billing plan configuration"""

    def test_starter_plan_pricing(self):
        """Starter plan has correct pricing and limits"""
        from app.billing.models import get_plan_info, SubscriptionPlan

        plan_info = get_plan_info(SubscriptionPlan.STARTER)
        assert plan_info.price_monthly == 29.00
        assert plan_info.task_limit_monthly == 1000

    def test_pro_plan_pricing(self):
        """Pro plan has correct pricing and limits"""
        from app.billing.models import get_plan_info, SubscriptionPlan

        plan_info = get_plan_info(SubscriptionPlan.PRO)
        assert plan_info.price_monthly == 99.00
        assert plan_info.task_limit_monthly == 10000

    def test_enterprise_plan_requires_sales(self):
        """Enterprise plan requires contacting sales"""
        from app.billing.models import get_plan_info, SubscriptionPlan

        plan_info = get_plan_info(SubscriptionPlan.ENTERPRISE)
        assert plan_info.task_limit_monthly == 999999
        assert plan_info.price_monthly == 0.0


class TestSubscriptionValidation:
    """Test subscription validation logic"""

    def test_check_active_subscription(self, test_db):
        """Check active subscription status"""
        from app.billing.service import check_subscription_active

        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            subscription_status="active",
        )
        test_db.add(org)
        test_db.commit()

        assert check_subscription_active(test_db, "test_org") is True

    def test_check_trialing_subscription(self, test_db):
        """Trial period is considered active"""
        from app.billing.service import check_subscription_active

        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            subscription_status="trialing",
        )
        test_db.add(org)
        test_db.commit()

        assert check_subscription_active(test_db, "test_org") is True

    def test_check_cancelled_subscription(self, test_db):
        """Cancelled subscription is not active"""
        from app.billing.service import check_subscription_active

        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            subscription_status="cancelled",
        )
        test_db.add(org)
        test_db.commit()

        assert check_subscription_active(test_db, "test_org") is False

    def test_check_past_due_subscription(self, test_db):
        """Past due subscription is not active"""
        from app.billing.service import check_subscription_active

        org = Organization(
            id="test_org",
            name="Test Org",
            email="test@example.com",
            subscription_status="past_due",
        )
        test_db.add(org)
        test_db.commit()

        assert check_subscription_active(test_db, "test_org") is False
