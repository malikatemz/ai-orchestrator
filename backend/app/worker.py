from __future__ import annotations

import json
import logging
from random import randint
from typing import Any

import sentry_sdk
from celery import Celery

from .config import settings
from .error_handling import ErrorCode
from .models import Task, Workflow, Organization, UsageRecord
from .database import SessionLocal
from .observability import configure_logging, log_event
from .services import record_audit_event
from .time_utils import utc_now

# Phase 4: Celery Configuration
celery = Celery("worker", broker=settings.redis_url, backend=settings.redis_url)

# Configure Celery with production settings
celery.conf.update(
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
)

logger = configure_logging()


def _build_result(task: Task) -> str:
    """Build execution result for development/demo mode.
    
    Generates a mock execution summary with confidence scoring
    based on input characteristics for demo/development environments.
    
    Algorithm:
    - Base confidence: 72%
    - Increase: +0.1% per 1000 input chars
    - Penalty: -5% per risk marker detected
    - Min: 52%, Max: 97%
    
    Risk markers: 'urgent', 'blocked', 'incident', 'risk'
    
    Args:
        task: Task record with input_data and agent type
        
    Returns:
        JSON string with execution summary including:
        - agent: Agent type that processed task
        - stage: 'completed'
        - summary: Processing description
        - recommended_next_step: Routing suggestion
        - confidence: Execution confidence (0.52-0.97)
        - signals: Input characteristics
        - deliverable: Output summary
        
    Example:
        >>> task = Task(agent="researcher", input_data="Urgent analysis...")
        >>> result_json = _build_result(task)
        >>> result = json.loads(result_json)
        >>> result["confidence"]
        0.67
    """
    input_text = task.input_data or ""
    risk_markers = sum(keyword in input_text.lower() for keyword in ["urgent", "blocked", "incident", "risk"])
    confidence = max(0.52, min(0.97, 0.72 + (len(input_text) / 1000) - (risk_markers * 0.05)))
    execution_summary = {
        "agent": task.agent,
        "stage": "completed",
        "summary": f"{task.agent.title()} agent processed task '{task.name}' and produced an orchestration-ready brief.",
        "recommended_next_step": "handoff-to-review" if task.agent in {"planner", "researcher"} else "ship-to-execution",
        "confidence": round(confidence, 2),
        "signals": {
            "input_length": len(input_text),
            "risk_markers": risk_markers,
            "estimated_tokens": max(40, len(input_text.split()) * 18),
        },
        "deliverable": f"Processed input: {input_text}",
    }
    return json.dumps(execution_summary)


@celery.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    time_limit=30 * 60,  # 30 minutes
    soft_time_limit=25 * 60,  # 25 minutes
)
def run_task(self, task_id: int, attempt: int = 0, failed_providers: list[str] | None = None) -> dict[str, Any]:
    """Execute task with intelligent provider routing and fallback chain.
    
    This is the core task execution worker. It implements:
    
    1. TASK LOADING
       - Fetch task and workflow from database
       - Validate task exists and is in correct state
       - Mark task as running
    
    2. PROVIDER ROUTING (Phase 4 - Intelligent Selection)
       Algorithm selects best provider based on:
       - Success rate (50% weight)
       - Average latency (30% weight)
       - Cost per request (20% weight)
       - Excludes providers that failed in previous attempts
       
    3. TASK EXECUTION
       - Demo/dev mode: Generate mock result with confidence scoring
       - Production mode: Call actual provider via execute_with_provider()
       - Measure execution time
       - Handle timeouts (30min hard limit, 25min soft limit)
    
    4. SUCCESS HANDLING
       - Update task status to 'completed'
       - Record usage for billing
       - Emit audit log
       - Return result summary
    
    5. FALLBACK CHAIN (Max 3 attempts)
       - On provider failure: Try next highest-scored provider
       - Exponential backoff: 60s, 120s, 240s delays
       - Track failed providers to avoid re-trying
       - After max attempts, mark task as failed
    
    6. ERROR HANDLING
       - Catch all exceptions and log to Sentry
       - Update task with error message
       - Mark task as failed
       - Record audit log with failure details
    
    Args:
        self: Celery task context (for retry())
        task_id: Task ID to execute
        attempt: Current retry attempt (0 = initial, max 3)
        failed_providers: List of providers that failed in previous attempts
        
    Returns:
        Dictionary with result:
        - On success:
          - status: "completed"
          - result: JSON output from provider/demo
          - provider: Provider name used
          - duration_seconds: Execution time
        - On failure:
          - status: "failed"
          - error: Error message
          - attempts: Total attempts made
        - On routing error:
          - status: "error"
          - message: Routing error message
          - code: ErrorCode enum value
    
    Raises:
        Exception: Caught and handled internally (task marked failed)
        
    Side Effects:
        - Updates Task status, output, timestamps in database
        - Creates UsageRecord for billing
        - Records AuditLog entries
        - Logs to application logger and Sentry
        - May retry task with exponential backoff
        
    Timeout Handling:
        - Soft limit (25min): SoftTimeLimitExceeded caught, task retried
        - Hard limit (30min): Task forcefully killed by Celery
        
    Example:
        >>> # Queue task (called by routes.py)
        >>> run_task.apply_async(args=[123], queue="default")
        
        >>> # Direct execution (fallback if queue down)
        >>> result = run_task.run(123)
        >>> result["status"]
        "completed"
    """
    
    db = SessionLocal()
    task = None
    failed_providers = failed_providers or []
    max_attempts = 3
    
    try:
        # ===== FETCH TASK =====
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"status": "error", "message": "Task not found", "code": ErrorCode.TASK_NOT_FOUND}
        
        workflow = db.query(Workflow).filter(Workflow.id == task.workflow_id).first()
        now = utc_now()
        
        # Update status to running
        task.status = "running"
        task.stage = "execution"
        task.started_at = now
        task.retries = attempt
        task.error_message = None
        
        if workflow:
            workflow.last_run_at = now
        
        db.commit()
        
        logger.info(f"Task {task_id} execution started (attempt {attempt + 1})")
        
        # ===== PROVIDER ROUTING (Phase 4) =====
        try:
            from .agents.router import route_task
            
            provider_name = route_task(
                db,
                task_id,
                attempt=attempt,
                exclude_providers=failed_providers,
            )
            logger.info(f"Task {task_id}: Selected provider {provider_name}")
            
        except Exception as e:
            logger.error(f"Task {task_id}: Provider selection failed: {str(e)}")
            task.status = "failed"
            task.stage = "failed"
            task.error_message = f"No provider available: {str(e)}"
            task.completed_at = utc_now()
            db.commit()
            return {"status": "error", "message": str(e)}
        
        # ===== TASK EXECUTION =====
        start_time = utc_now()
        
        try:
            # For production: use actual provider
            # For development: use mock result
            from .config import AppMode
            
            if settings.app_mode == AppMode.DEMO or settings.app_mode == AppMode.DEVELOPMENT:
                # Demo/development mode: return mock result
                task.stage = "execution"
                task.duration_seconds = round(randint(8, 42) / 10, 1)
                task.output_data = _build_result(task)
                result_success = True
            else:
                # Production: use actual provider
                from .agents.executor import execute_with_provider
                
                result = execute_with_provider(
                    provider_name,
                    task.input_data,
                    max_tokens=2000,
                )
                task.output_data = str(result.get("output", ""))
                duration = (utc_now() - start_time).total_seconds()
                task.duration_seconds = duration
                result_success = True
            
            # ===== SUCCESS =====
            task.status = "completed"
            task.stage = "completed"
            task.completed_at = utc_now()
            db.commit()
            
            # Record usage for billing
            org = workflow.organization if workflow else None
            if org:
                usage = UsageRecord(
                    org_id=org.id,
                    task_id=task_id,
                    usage_type="task_execution",
                    quantity=1,
                )
                db.add(usage)
                db.commit()
            
            record_audit_event(
                db,
                actor="system",
                event="task_completed",
                resource_type="task",
                resource_id=task.id,
                details={
                    "workflow_id": task.workflow_id,
                    "provider": provider_name,
                    "duration_seconds": task.duration_seconds,
                    "attempt": attempt + 1,
                },
            )
            
            logger.info(f"Task {task_id} completed with {provider_name} in {task.duration_seconds}s")
            
            return {
                "status": "completed",
                "result": task.output_data,
                "provider": provider_name,
                "duration_seconds": task.duration_seconds,
            }
        
        except Exception as e:
            logger.warning(f"Task {task_id}: Provider {provider_name} failed: {str(e)}")
            
            # ===== FALLBACK CHAIN =====
            if attempt < max_attempts:
                failed_providers.append(provider_name)
                retry_delay = 60 * (2 ** attempt)  # Exponential backoff
                
                logger.info(f"Task {task_id}: Fallback {attempt + 2}/{max_attempts + 1} in {retry_delay}s")
                
                # Retry with exponential backoff
                raise self.retry(
                    args=[task_id, attempt + 1, failed_providers],
                    countdown=retry_delay,
                    exc=e,
                )
            
            raise
    
    except Exception as exc:
        logger.error(f"Task {task_id} final failure: {str(exc)}", exc_info=True)
        sentry_sdk.capture_exception(exc)
        
        if task:
            task.status = "failed"
            task.stage = "failed"
            task.error_message = str(exc)
            task.completed_at = utc_now()
            db.commit()
            
            record_audit_event(
                db,
                actor="system",
                event="task_failed",
                resource_type="task",
                resource_id=task.id,
                details={
                    "workflow_id": task.workflow_id,
                    "queue_name": task.queue_name,
                    "error": str(exc),
                    "attempt": attempt + 1,
                    "failed_providers": failed_providers,
                },
            )
            
            logger.error(f"Task {task_id} failed after {attempt + 1} attempts")
        
        return {"status": "failed", "error": str(exc), "attempts": attempt + 1}
    
    finally:
        db.close()


def queue_task(task_id: int, queue_name: str = "default") -> str:
    """Queue a task for asynchronous execution.
    
    Routes task to Celery worker via specified queue.
    If Celery is unavailable, falls back to inline (synchronous) execution.
    
    Queue Types:
    - high_priority: SLA < 30s (for critical/urgent tasks)
    - default: SLA < 5min (standard tasks)
    - low_cost: SLA < 1hr (background/optimized cost tasks)
    
    Args:
        task_id: Task ID to queue
        queue_name: Celery queue name (default: "default")
        
    Returns:
        Queue mode indicator:
        - "celery": Task successfully queued (async)
        - "inline": Queue unavailable, ran synchronously (fallback)
        
    Side Effects:
        - Emits 'queue_dispatch' log on success
        - Emits 'queue_degraded' log on fallback
        - Executes task immediately if queue unavailable
        
    Error Handling:
        - ConnectionError: Fall back to inline execution
        - Any other exception: Log to Sentry, try inline
        
    Example:
        >>> result = queue_task(task_id=123, queue_name="high_priority")
        >>> result
        "celery"  # or "inline" if fallback triggered
        
    Note:
        The fallback behavior ensures no tasks are lost due to
        queue unavailability, at the cost of blocking the request.
    """
    try:
        run_task.apply_async(args=[task_id], queue=queue_name)
        log_event(logger, "info", "queue_dispatch", task_id=task_id, queue_name=queue_name, queue_mode="celery")
        return "celery"
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        log_event(
            logger,
            "warning",
            "queue_degraded",
            code=ErrorCode.QUEUE_DEGRADED,
            task_id=task_id,
            queue_name=queue_name,
            queue_mode="inline",
            error=str(exc),
        )
        run_task.run(task_id)
        return "inline"
