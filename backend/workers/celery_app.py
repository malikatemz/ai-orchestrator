"""Celery worker application and task definitions"""

from celery import Celery
from celery.signals import task_postrun, task_prerun
import logging

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models import Task, UsageRecord

logger = logging.getLogger(__name__)

# Initialize Celery app
app = Celery(
    'ai_orchestrator',
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,  # Results expire after 1 hour
)

# Task routing to queues based on priority
app.conf.task_routes = {
    'backend.workers.tasks.execute_task': {'queue': 'default'},
    'backend.workers.tasks.execute_high_priority_task': {'queue': 'high_priority'},
    'backend.workers.tasks.report_usage': {'queue': 'reporting'},
}

# Queue configuration
app.conf.task_queues = (
    # Default queue for standard tasks
    {
        'name': 'default',
        'exchange': 'default',
        'routing_key': 'default',
        'priority': 5,
    },
    # High priority queue (for critical workflows)
    {
        'name': 'high_priority',
        'exchange': 'high_priority',
        'routing_key': 'high_priority',
        'priority': 9,
    },
    # Reporting/analytics queue (low priority)
    {
        'name': 'reporting',
        'exchange': 'reporting',
        'routing_key': 'reporting',
        'priority': 1,
    },
)


@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **kw):
    """Log task start"""
    logger.info(f"Task {task.name} (ID: {task_id}) started")


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, state, **kw):
    """Log task completion"""
    logger.info(f"Task {task.name} (ID: {task_id}) completed with state: {state}")


@app.task(
    name='backend.workers.tasks.execute_task',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def execute_task(self, task_id: int):
    """
    Execute a single task using agent routing with fallback chain.
    
    Args:
        task_id: Database task ID to execute
    
    Returns:
        dict with execution result
    """
    db = SessionLocal()
    try:
        from backend.app.agents.router import route_task
        from backend.app.agents.scorer import should_fallback_to_next
        from backend.app.billing.service import report_usage
        from backend.app.time_utils import utc_now
        from backend.app.models import Task as TaskModel
        
        # Fetch task from database
        task_db = db.query(TaskModel).filter_by(id=task_id).first()
        if not task_db:
            logger.error(f"Task {task_id} not found")
            return {"error": "Task not found", "task_id": task_id}
        
        # Mark task as running
        task_db.status = "running"
        task_db.started_at = utc_now()
        db.commit()
        
        # Route and execute with fallback chain
        result = None
        fallback_count = 0
        max_fallbacks = 3
        
        while fallback_count <= max_fallbacks and result is None:
            try:
                # Get next provider via routing algorithm
                provider = route_task(db, task_id, attempt=fallback_count)
                
                logger.info(f"Task {task_id}: Executing with provider {provider}")
                
                # Execute task with selected provider
                from backend.app.services import execute_with_provider
                result = execute_with_provider(provider, task_db.input_data)
                
                # Check if result is acceptable
                if not should_fallback_to_next(result, provider):
                    break
                
                fallback_count += 1
                logger.warning(f"Task {task_id}: Fallback {fallback_count} to next provider")
                
            except Exception as e:
                logger.error(f"Task {task_id}: Provider error: {str(e)}")
                fallback_count += 1
                if fallback_count > max_fallbacks:
                    raise
        
        if result is None:
            raise Exception("All providers exhausted, no successful result")
        
        # Mark task as completed
        task_db.status = "completed"
        task_db.output_data = str(result)
        task_db.completed_at = utc_now()
        duration = (task_db.completed_at - task_db.started_at).total_seconds()
        task_db.duration_seconds = duration
        db.commit()
        
        # Record usage for billing
        if task_db.workflow.organization:
            usage = UsageRecord(
                org_id=task_db.workflow.organization.id,
                task_id=task_id,
                usage_type="task_execution",
                quantity=1,
            )
            db.add(usage)
            db.commit()
            
            # Report to Stripe (background, non-blocking)
            try:
                report_usage.apply_async(
                    args=[task_db.workflow.organization.id],
                    queue='reporting',
                )
            except Exception as e:
                logger.warning(f"Failed to report usage: {str(e)}")
        
        logger.info(f"Task {task_id} completed successfully")
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result,
            "duration_seconds": duration,
        }
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}", exc_info=True)
        
        # Update task status to failed
        try:
            task_db = db.query(TaskModel).filter_by(id=task_id).first()
            if task_db:
                task_db.status = "failed"
                task_db.error_message = str(e)
                task_db.completed_at = utc_now()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update task status: {str(db_error)}")
        
        # Retry with exponential backoff
        retry_delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=retry_delay)
        
    finally:
        db.close()


@app.task(
    name='backend.workers.tasks.report_usage',
    bind=True,
)
def report_usage(self, org_id: str):
    """
    Report organization usage to Stripe for metering.
    
    Args:
        org_id: Organization ID to report usage for
    """
    db = SessionLocal()
    try:
        from backend.app.models import Organization
        from backend.app.billing.service import report_usage as stripe_report_usage
        from datetime import timedelta
        from backend.app.time_utils import utc_now
        
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org:
            logger.warning(f"Organization {org_id} not found for usage reporting")
            return
        
        # Count tasks used in last hour
        one_hour_ago = utc_now() - timedelta(hours=1)
        recent_usage = db.query(UsageRecord).filter(
            UsageRecord.org_id == org_id,
            UsageRecord.created_at >= one_hour_ago,
        ).count()
        
        if recent_usage > 0 and org.subscription_item_id:
            stripe_report_usage(
                db,
                org_id,
                org.subscription_item_id,
                quantity=recent_usage,
            )
        
        logger.info(f"Reported {recent_usage} usage records for org {org_id}")
        return {"org_id": org_id, "usage_count": recent_usage}
        
    except Exception as e:
        logger.error(f"Failed to report usage for org {org_id}: {str(e)}", exc_info=True)
        return {"error": str(e), "org_id": org_id}
        
    finally:
        db.close()


@app.task(name='backend.workers.tasks.cleanup_old_results')
def cleanup_old_results():
    """Periodic task to clean up old task results"""
    db = SessionLocal()
    try:
        from backend.app.models import Task as TaskModel
        from datetime import timedelta
        from backend.app.time_utils import utc_now
        
        # Delete completed tasks older than 30 days
        cutoff = utc_now() - timedelta(days=30)
        deleted = db.query(TaskModel).filter(
            TaskModel.completed_at < cutoff,
            TaskModel.status == "completed",
        ).delete()
        
        db.commit()
        logger.info(f"Cleaned up {deleted} old task results")
        return {"cleaned_tasks": deleted}
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {"error": str(e)}
        
    finally:
        db.close()


# Periodic task schedule
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-old-results': {
        'task': 'backend.workers.tasks.cleanup_old_results',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
