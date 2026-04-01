"""Celery worker task execution with agent routing and provider fallback"""

from celery import shared_task
import logging
import time
from datetime import datetime
from typing import Optional, List

from .config import get_settings
from .database import SessionLocal
from .models import Task, TaskStatus, UsageRecord
from .agents.router import select_agent, record_provider_usage, get_fallback_chain
from .providers.executor import execute_task, TaskExecutionError
from .audit import log_event

logger = logging.getLogger(__name__)
settings = get_settings()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_task_async(
    self,
    task_id: int,
    org_id: str,
    task_type: str,
    input_json: dict,
    queue_name: str = "default",
    failed_providers: Optional[List[str]] = None,
) -> dict:
    """
    Execute task via selected provider with fallback chain.
    
    1. Select best provider for task type
    2. Execute task
    3. On failure: try fallback providers (up to 3)
    4. Record usage and update task status
    
    Returns:
      {
        "task_id": int,
        "status": str,
        "output": dict,
        "retries": int,
      }
    """
    
    failed_providers = failed_providers or []
    db = SessionLocal()
    
    try:
        # Get task from DB
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"status": "error", "message": "Task not found"}
        
        # Update status to RUNNING
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        db.commit()
        
        # Select best provider
        try:
            provider, alternatives = select_agent(db, task_type, exclude_providers=failed_providers)
        except Exception as e:
            logger.error(f"No provider available for {task_type}: {str(e)}")
            task.status = TaskStatus.FAILED
            task.error_message = f"No provider available: {str(e)}"
            db.commit()
            log_event(
                db=db,
                user_id=str(task.user_id),
                org_id=str(org_id),
                action="task.failed",
                resource_type="task",
                resource_id=task_id,
                details={"error": "no_provider", "task_type": task_type},
            )
            return {"status": "failed", "message": str(e), "task_id": task_id}
        
        # Execute task
        start_time = time.time()
        execution_error = None
        
        try:
            logger.info(f"Executing task {task_id} with provider {provider.id}")
            result = execute_task(provider, task_type, input_json)
            
            # Record successful execution
            latency_ms = result["latency_ms"]
            cost_usd = result["cost_usd"]
            output_json = result["output"]
            
            record_provider_usage(
                db,
                org_id,
                provider.id,
                task_type,
                success=True,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                token_count=result.get("tokens_used", 0),
            )
            
            # Update task with output
            task.status = TaskStatus.COMPLETED
            task.output_json = output_json
            task.selected_provider = provider.id
            task.completed_at = datetime.utcnow()
            
            # Record usage for billing
            usage = UsageRecord(
                org_id=org_id,
                user_id=task.user_id,
                task_id=task_id,
                task_type=task_type,
                provider=provider.id,
                input_tokens=0,
                output_tokens=result.get("tokens_used", 0),
                cost_usd=cost_usd,
                duration_ms=latency_ms,
            )
            db.add(usage)
            db.commit()
            
            logger.info(f"Task {task_id} completed: {provider.id}, cost=${cost_usd:.4f}")
            
            log_event(
                db=db,
                user_id=str(task.user_id),
                org_id=str(org_id),
                action="task.completed",
                resource_type="task",
                resource_id=task_id,
                details={
                    "provider": provider.id,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                },
            )
            
            return {
                "status": "completed",
                "task_id": task_id,
                "output": output_json,
                "provider": provider.id,
            }
        
        except TaskExecutionError as e:
            execution_error = str(e)
            logger.warning(f"Provider {provider.id} failed for task {task_id}: {execution_error}")
            
            # Record failure in stats
            record_provider_usage(
                db,
                org_id,
                provider.id,
                task_type,
                success=False,
                latency_ms=int((time.time() - start_time) * 1000),
                cost_usd=0.0,
            )
            
            # Try fallback providers
            if len(failed_providers) < 3:
                failed_providers.append(provider.id)
                fallback_chain = get_fallback_chain(db, task_type, failed_providers, max_fallbacks=3)
                
                if fallback_chain:
                    logger.info(f"Retrying task {task_id} with fallback provider")
                    # Retry with fallback
                    return execute_task_async.apply_async(
                        args=[task_id, org_id, task_type, input_json],
                        kwargs={"queue_name": queue_name, "failed_providers": failed_providers},
                        countdown=10,  # Wait 10 seconds before retry
                    )
            
            # All providers failed
            task.status = TaskStatus.FAILED
            task.error_message = f"All providers failed. Last error: {execution_error}"
            task.completed_at = datetime.utcnow()
            db.commit()
            
            log_event(
                db=db,
                user_id=str(task.user_id),
                org_id=str(org_id),
                action="task.failed",
                resource_type="task",
                resource_id=task_id,
                details={
                    "error": execution_error,
                    "failed_providers": failed_providers,
                    "task_type": task_type,
                },
            )
            
            return {
                "status": "failed",
                "task_id": task_id,
                "error": execution_error,
                "failed_providers": failed_providers,
            }
    
    except Exception as e:
        logger.exception(f"Unexpected error in execute_task_async: {str(e)}")
        return {"status": "error", "message": str(e), "task_id": task_id}
    
    finally:
        db.close()


# ============ Scheduled Tasks ============

@shared_task
def cleanup_old_tasks():
    """Clean up completed tasks older than 30 days"""
    from datetime import timedelta
    
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        deleted = db.query(Task).filter(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at < cutoff,
        ).delete()
        db.commit()
        logger.info(f"Cleaned up {deleted} old tasks")
    finally:
        db.close()


@shared_task
def calculate_daily_metrics():
    """Calculate and cache daily metrics"""
    from sqlalchemy import func
    from .models import TaskStatus
    
    db = SessionLocal()
    try:
        total = db.query(func.count(Task.id)).scalar()
        completed = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.COMPLETED).scalar()
        failed = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.FAILED).scalar()
        
        success_rate = (completed / total * 100) if total > 0 else 0
        
        logger.info(f"Daily metrics: {total} tasks, {success_rate:.1f}% success rate")
    finally:
        db.close()
