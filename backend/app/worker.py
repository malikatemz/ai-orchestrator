import json
from datetime import datetime
from random import randint
from typing import Dict, Any

import sentry_sdk
from celery import Celery

from .config import settings
from .error_handling import ErrorCode
from .models import Task, Workflow
from .database import SessionLocal
from .observability import configure_logging, log_event

celery = Celery("worker", broker=settings.redis_url, backend=settings.redis_url)
logger = configure_logging()


def _build_result(task: Task) -> str:
    """Build mock execution result for a task."""
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


@celery.task(bind=True, autoretry_for=(ConnectionError, TimeoutError), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 5})
def run_task(self, task_id: int) -> Dict[str, Any]:
    """Execute a task asynchronously."""
    db = SessionLocal()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            log_event(logger, "warning", "task_missing", code=ErrorCode.TASK_NOT_FOUND, task_id=task_id)
            return {"status": "error", "message": "Task not found", "code": ErrorCode.TASK_NOT_FOUND}

        workflow = db.query(Workflow).filter(Workflow.id == task.workflow_id).first()
        now = datetime.utcnow()
        log_event(logger, "info", "task_started", task_id=task.id, workflow_id=task.workflow_id, agent=task.agent, retry_count=task.retries)
        task.status = "running"
        task.stage = "analysis"
        task.started_at = now
        task.error_message = None
        if workflow:
            workflow.last_run_at = now
        db.commit()

        task.stage = "execution"
        task.duration_seconds = round(randint(8, 42) / 10, 1)
        task.output_data = _build_result(task)
        task.status = "completed"
        task.stage = "completed"
        task.completed_at = datetime.utcnow()
        db.commit()
        log_event(
            logger,
            "info",
            "task_completed",
            task_id=task.id,
            workflow_id=task.workflow_id,
            duration_seconds=task.duration_seconds,
            retry_count=task.retries,
        )

        return {"status": "completed", "result": task.output_data}
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        if task:
            task.status = "failed"
            task.stage = "failed"
            task.error_message = str(exc)
            task.retries += 1
            task.completed_at = datetime.utcnow()
            db.commit()
            log_event(
                logger,
                "error",
                "task_failed",
                code=ErrorCode.TASK_RETRY_EXHAUSTED,
                task_id=task.id,
                workflow_id=task.workflow_id,
                retry_count=task.retries,
                error=str(exc),
            )
        return {"status": "failed", "error": str(exc), "code": ErrorCode.TASK_RETRY_EXHAUSTED}
    finally:
        db.close()


def queue_task(task_id: int) -> str:
    try:
        run_task.delay(task_id)
        log_event(logger, "info", "queue_dispatch", task_id=task_id, queue_mode="celery")
        return "celery"
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        log_event(logger, "warning", "queue_degraded", code=ErrorCode.QUEUE_DEGRADED, task_id=task_id, queue_mode="inline", error=str(exc))
        run_task.run(task_id)
        return "inline"
