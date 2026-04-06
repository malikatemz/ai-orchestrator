from __future__ import annotations

import json
import logging
from random import randint
from typing import Any, Dict

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
    """Build execution result for development/demo mode"""
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
def run_task(self, task_id: int, attempt: int = 0, failed_providers: list = None) -> Dict[str, Any]:
    """Phase 4: Execute task with provider routing and fallback chain
    
    This worker task:
    1. Selects best provider using scoring algorithm
    2. Executes task with selected provider
    3. Falls back to next provider on failure (max 3 fallbacks)
    4. Records usage for billing
    5. Reports to Stripe if applicable
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
                queue_name=task.queue_name,
                retry_count=task.retries,
                error=str(exc),
            )
        return {"status": "failed", "error": str(exc), "code": ErrorCode.TASK_RETRY_EXHAUSTED}
    finally:
        db.close()


def queue_task(task_id: int, queue_name: str = "default") -> str:
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
