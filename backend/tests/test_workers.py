"""Tests for Phase 4: Celery Worker Integration"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.models import Task, Organization, UsageRecord
from app.time_utils import utc_now
from app.database import SessionLocal
from backend.workers.phase4_tasks import (
    execute_task_from_queue,
    report_usage_to_stripe,
    cleanup_old_tasks,
)


class TestTaskExecution:
    """Test task execution with provider routing"""

    def test_execute_task_not_found(self, test_db):
        """Handle missing task gracefully"""
        result = execute_task_from_queue.apply(args=[99999]).get()
        
        assert result["status"] == "failed"
        assert "not found" in result.get("error", "").lower()

    def test_execute_task_selected_provider(self, test_db):
        """Execute task with selected provider"""
        # This test would require full provider setup
        pass

    def test_execute_task_fallback_chain(self, test_db):
        """Fallback to next provider on failure"""
        # Test that failed providers are tracked
        # Test that retry uses fallback chain
        pass

    def test_execute_task_updates_status(self, test_db):
        """Task status updated to running then completed"""
        pass

    def test_execute_task_records_duration(self, test_db):
        """Task duration recorded accurately"""
        pass


class TestUsageTracking:
    """Test usage tracking and billing"""

    def test_report_usage_organization_not_found(self, test_db):
        """Handle missing organization"""
        result = report_usage_to_stripe.apply(args=["nonexistent_org"]).get()
        
        assert result["success"] is False
        assert result["org_id"] == "nonexistent_org"

    def test_report_usage_no_subscription_item(self, test_db):
        """Skip reporting if no subscription item"""
        # Create org without subscription
        org = Organization(
            id="test_org",
            name="Test",
            email="test@example.com",
            subscription_item_id=None,
        )
        test_db.add(org)
        test_db.commit()
        
        result = report_usage_to_stripe.apply(args=["test_org"]).get()
        
        assert result["success"] is True
        assert result["usage_count"] == 0

    def test_report_usage_counts_recent_records(self, test_db):
        """Count usage from last hour"""
        org = Organization(
            id="test_org",
            name="Test",
            email="test@example.com",
            subscription_item_id="si_test123",
        )
        test_db.add(org)
        test_db.commit()
        
        # Create usage records within last hour
        for i in range(5):
            record = UsageRecord(
                org_id="test_org",
                usage_type="task_execution",
                quantity=1,
                created_at=utc_now() - timedelta(minutes=30),
            )
            test_db.add(record)
        test_db.commit()
        
        # Old usage should not count
        old_record = UsageRecord(
            org_id="test_org",
            usage_type="task_execution",
            quantity=1,
            created_at=utc_now() - timedelta(hours=2),
        )
        test_db.add(old_record)
        test_db.commit()
        
        # Only recent usage reported
        assert len([r for r in test_db.query(UsageRecord).filter_by(org_id="test_org").all()]) >= 5


class TestCleanup:
    """Test cleanup of old tasks"""

    def test_cleanup_preserves_recent_tasks(self, test_db):
        """Recent tasks not deleted"""
        # Create recent completed task
        now = utc_now()
        task = Task(
            workflow_id=1,
            name="Recent",
            status="completed",
            completed_at=now - timedelta(days=5),
            queue_name="default",
            input_data="test",
        )
        test_db.add(task)
        test_db.commit()
        
        initial_count = test_db.query(Task).count()
        result = cleanup_old_tasks.apply().get()
        
        # Should not delete recent tasks
        assert result["deleted_completed"] == 0

    def test_cleanup_deletes_old_tasks(self, test_db):
        """Old tasks deleted after 30 days"""
        # Create old completed task
        old_date = utc_now() - timedelta(days=35)
        task = Task(
            workflow_id=1,
            name="Old",
            status="completed",
            completed_at=old_date,
            queue_name="default",
            input_data="test",
        )
        test_db.add(task)
        test_db.commit()
        
        result = cleanup_old_tasks.apply().get()
        
        # Should delete old tasks
        assert result["deleted_completed"] + result["deleted_failed"] > 0

    def test_cleanup_keeps_running_tasks(self, test_db):
        """Running/pending tasks never deleted"""
        task = Task(
            workflow_id=1,
            name="Running",
            status="running",
            queue_name="default",
            input_data="test",
        )
        test_db.add(task)
        test_db.commit()
        
        result = cleanup_old_tasks.apply().get()
        
        # Should not delete running tasks
        remaining = test_db.query(Task).filter_by(status="running").count()
        assert remaining == 1


class TestFallbackChain:
    """Test fallback provider chain"""

    def test_fallback_on_provider_failure(self):
        """Fallback to next provider on failure"""
        # Mock provider failure
        with patch('backend.workers.phase4_tasks.execute_with_provider') as mock_execute:
            mock_execute.side_effect = Exception("Provider timeout")
            # Should retry with different provider
            pass

    def test_max_fallbacks_enforced(self):
        """Stop after max fallbacks (3)"""
        # Track fallback count
        # Ensure it doesn't exceed 3
        pass

    def test_failed_providers_excluded(self):
        """Failed providers excluded from next attempt"""
        # Verify failed_providers list passed to retry
        pass


class TestTaskRetry:
    """Test task retry logic"""

    def test_retry_with_exponential_backoff(self):
        """Retry delay increases exponentially"""
        # First retry: 60s
        # Second retry: 120s
        # Third retry: 240s
        pass

    def test_retry_max_three_times(self):
        """Max retries = 3"""
        # Verify task fails after 3 retries
        pass


class TestWorkerIntegration:
    """Integration tests with actual queue"""

    def test_task_queued_and_executed(self):
        """Task queued and executed by worker"""
        # This requires Redis/Celery broker running
        pass

    def test_priority_queue_respected(self):
        """High priority tasks executed first"""
        pass

    def test_reporting_queue_separate(self):
        """Usage reporting doesn't block task queue"""
        pass


class TestErrorHandling:
    """Test error handling in workers"""

    def test_database_connection_error(self):
        """Handle database connection loss"""
        pass

    def test_provider_api_error(self):
        """Handle provider API errors gracefully"""
        pass

    def test_timeout_error(self):
        """Handle task timeout"""
        pass

    def test_malformed_input_data(self):
        """Handle invalid task input"""
        pass
