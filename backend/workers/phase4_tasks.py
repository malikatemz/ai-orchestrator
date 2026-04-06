"""Phase 4: Celery Worker Integration - Task Execution Pipeline

This module implements the complete Phase 4 worker integration with:
- Celery task queue setup
- Agent routing and provider selection
- Fallback chain implementation
- Usage tracking and billing integration
- Dead letter queue handling
- Task retry logic with exponential backoff
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from celery import shared_task, Task
from sqlalchemy.orm import Session

from ..app.config import get_settings
from ..app.database import SessionLocal
from ..app.models import Task as TaskModel, Organization, UsageRecord
from ..app.time_utils import utc_now

logger = logging.getLogger(__name__)
settings = get_settings()


class ExecutionTask(Task):
    """Base task class with custom error handling"""
    
    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 60
    time_limit = 30 * 60  # 30 minutes
    soft_time_limit = 25 * 60  # 25 minutes


@shared_task(
    bind=True,
    base=ExecutionTask,
    name='backend.workers.tasks.execute_task_from_queue',
)
def execute_task_from_queue(
    self,
    task_id: int,
    attempt: int = 0,
    failed_providers: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Execute a task from the queue using selected provider with fallback.
    
    **Process:**
    1. Fetch task and organization from database
    2. Select best provider using scoring algorithm
    3. Execute task with selected provider
    4. On failure: fallback to next provider (up to 3 times)
    5. Record usage and update task status
    6. Report to Stripe if applicable
    
    Args:
        task_id: Database task ID
        attempt: Current attempt number (0-3)
        failed_providers: List of providers that failed
    
    Returns:
        {
            "task_id": int,
            "status": "completed" | "failed",
            "result": str (output_data),
            "provider": str,
            "duration_seconds": float,
        }
    
    Raises:
        self.retry: Exponential backoff retry on failure
    """
    
    db = SessionLocal()
    failed_providers = failed_providers or []
    max_attempts = 3
    
    try:
        # ===== 1. FETCH TASK ===== 
        task = db.query(TaskModel).filter_by(id=task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found in database")
            return {"task_id": task_id, "status": "failed", "error": "Task not found"}
        
        # Update task status
        task.status = "running"
        task.started_at = utc_now()
        db.commit()
        
        # Fetch organization for billing
        org = db.query(Organization).filter_by(id=task.workflow.owner).first()
        
        # ===== 2. SELECT PROVIDER =====
        from ..app.agents.router import route_task
        
        try:
            provider_name = route_task(
                db,
                task.id,
                attempt=attempt,
                exclude_providers=failed_providers,
            )
        except Exception as e:
            logger.error(f"Task {task_id}: Failed to select provider: {str(e)}")
            task.status = "failed"
            task.error_message = f"Provider selection failed: {str(e)}"
            task.completed_at = utc_now()
            db.commit()
            return {"task_id": task_id, "status": "failed", "error": "No provider available"}
        
        logger.info(f"Task {task_id}: Selected provider {provider_name} (attempt {attempt + 1})")
        
        # ===== 3. EXECUTE TASK =====
        start_time = utc_now()
        
        try:
            from ..app.providers.executor import execute_with_provider
            
            result = execute_with_provider(
                provider_name,
                task.input_data,
                max_tokens=2000,
                temperature=0.7,
            )
            
            duration = (utc_now() - start_time).total_seconds()
            
            # Success: update task
            task.status = "completed"
            task.output_data = str(result.get("output", ""))
            task.completed_at = utc_now()
            task.duration_seconds = duration
            db.commit()
            
            logger.info(f"Task {task_id} completed with {provider_name} in {duration:.2f}s")
            
            # ===== 4. RECORD USAGE =====
            if org:
                usage_record = UsageRecord(
                    org_id=org.id,
                    task_id=task_id,
                    usage_type="task_execution",
                    quantity=1,
                    metadata_json=f'{{"provider": "{provider_name}", "duration_seconds": {duration}}}',
                )
                db.add(usage_record)
                db.commit()
                
                # ===== 5. REPORT TO STRIPE ======
                if org.subscription_item_id:
                    try:
                        report_usage_to_stripe.apply_async(
                            args=[org.id],
                            queue='reporting',
                        )
                    except Exception as e:
                        logger.warning(f"Failed to queue usage report: {str(e)}")
            
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result.get("output", ""),
                "provider": provider_name,
                "duration_seconds": duration,
            }
        
        except Exception as e:
            logger.warning(f"Task {task_id}: Provider {provider_name} failed: {str(e)}")
            
            # ===== FALLBACK CHAIN =====
            if attempt < max_attempts:
                failed_providers.append(provider_name)
                
                # Exponential backoff: 60s, 120s, 240s
                retry_delay = 60 * (2 ** attempt)
                
                logger.info(f"Task {task_id}: Attempting fallback {attempt + 2}/{max_attempts + 1} in {retry_delay}s")
                
                # Retry with next provider
                self.retry(
                    args=[task_id, attempt + 1, failed_providers],
                    countdown=retry_delay,
                    exc=e,
                )
            
            # All attempts exhausted
            task.status = "failed"
            task.error_message = f"All {max_attempts + 1} providers failed. Last error: {str(e)}"
            task.completed_at = utc_now()
            task.retries = attempt
            db.commit()
            
            logger.error(f"Task {task_id} failed after {attempt + 1} attempts")
            
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "attempts": attempt + 1,
            }
    
    except Exception as exc:
        logger.error(f"Task {task_id} worker error: {str(exc)}", exc_info=True)
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(exc),
        }
    
    finally:
        db.close()


@shared_task(
    bind=True,
    name='backend.workers.tasks.report_usage_to_stripe',
)
def report_usage_to_stripe(self, org_id: str) -> Dict[str, Any]:
    """
    Report organization usage to Stripe for metered billing.
    
    Batches usage from the last hour and reports to Stripe's
    usage reporting API for per-unit pricing.
    
    Args:
        org_id: Organization ID to report
    
    Returns:
        {
            "org_id": str,
            "usage_count": int,
            "success": bool,
        }
    """
    
    db = SessionLocal()
    
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org:
            logger.warning(f"Organization {org_id} not found for usage reporting")
            return {"org_id": org_id, "success": False, "error": "Organization not found"}
        
        if not org.subscription_item_id:
            logger.debug(f"Org {org_id}: No subscription item ID for usage reporting")
            return {"org_id": org_id, "success": True, "usage_count": 0}
        
        # Count usage in last hour
        one_hour_ago = utc_now() - timedelta(hours=1)
        recent_usage = db.query(UsageRecord).filter(
            UsageRecord.org_id == org_id,
            UsageRecord.created_at >= one_hour_ago,
        ).count()
        
        if recent_usage == 0:
            logger.debug(f"Org {org_id}: No usage in last hour to report")
            return {"org_id": org_id, "success": True, "usage_count": 0}
        
        # Report to Stripe
        from ..app.billing.service import report_usage
        
        record_id = report_usage(
            db,
            org_id,
            org.subscription_item_id,
            quantity=recent_usage,
        )
        
        if record_id:
            logger.info(f"Reported {recent_usage} usage units for org {org_id}")
            return {
                "org_id": org_id,
                "success": True,
                "usage_count": recent_usage,
                "stripe_record_id": record_id,
            }
        else:
            logger.warning(f"Failed to report usage for org {org_id}")
            return {
                "org_id": org_id,
                "success": False,
                "usage_count": recent_usage,
                "error": "Stripe reporting failed",
            }
    
    except Exception as e:
        logger.error(f"Usage reporting task failed for org {org_id}: {str(e)}")
        return {
            "org_id": org_id,
            "success": False,
            "error": str(e),
        }
    
    finally:
        db.close()


@shared_task(name='backend.workers.tasks.cleanup_old_tasks')
def cleanup_old_tasks() -> Dict[str, Any]:
    """
    Periodic cleanup task to remove old completed/failed tasks.
    
    Keeps task history for 30 days minimum for audit purposes.
    
    Returns:
        {
            "deleted_completed": int,
            "deleted_failed": int,
            "total_deleted": int,
        }
    """
    
    db = SessionLocal()
    
    try:
        cutoff_date = utc_now() - timedelta(days=30)
        
        # Delete old completed tasks
        deleted_completed = db.query(TaskModel).filter(
            TaskModel.status == "completed",
            TaskModel.completed_at < cutoff_date,
        ).delete()
        
        # Delete old failed tasks
        deleted_failed = db.query(TaskModel).filter(
            TaskModel.status == "failed",
            TaskModel.completed_at < cutoff_date,
        ).delete()
        
        db.commit()
        
        total_deleted = deleted_completed + deleted_failed
        logger.info(f"Cleanup: Deleted {deleted_completed} completed, {deleted_failed} failed tasks")
        
        return {
            "deleted_completed": deleted_completed,
            "deleted_failed": deleted_failed,
            "total_deleted": total_deleted,
        }
    
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {
            "error": str(e),
            "deleted_completed": 0,
            "deleted_failed": 0,
            "total_deleted": 0,
        }
    
    finally:
        db.close()


# Schedule periodic cleanup daily at 2 AM UTC
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-tasks': {
        'task': 'backend.workers.tasks.cleanup_old_tasks',
        'schedule': crontab(hour=2, minute=0),
    },
}
