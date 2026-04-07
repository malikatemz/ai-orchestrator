from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from . import models, repositories
from .config import settings
from .error_handling import ApiError, ErrorCode, ErrorSeverity
from .time_utils import utc_now

SYSTEM_ACTOR = "system"
DEMO_ACTOR = "demo-guest"


def is_admin(user: dict[str, Any]) -> bool:
    """Check if user has admin privileges.
    
    Admin users can be identified by:
    1. Having 'admin' as their sub (user ID)
    2. Having 'orchestrator:admin' in their scopes list
    
    Args:
        user: User context dictionary with 'sub' and optional 'scopes'
        
    Returns:
        True if user is admin, False otherwise
        
    Example:
        >>> user = {"sub": "admin"}
        >>> is_admin(user)
        True
    """
    return user.get("sub") == "admin" or "orchestrator:admin" in user.get("scopes", [])


def can_manage_demo(user: dict[str, Any]) -> bool:
    """Check if user can manage demo data.
    
    Demo management is allowed if:
    1. Public demo mode is enabled (any user can manage)
    2. User is an admin
    
    Args:
        user: User context dictionary
        
    Returns:
        True if user can manage demo, False otherwise
        
    Example:
        >>> user = {"sub": "user-123", "scopes": ["orchestrator:admin"]}
        >>> can_manage_demo(user)
        True
    """
    return settings.public_demo_mode or is_admin(user)


def ensure_ops_access(user: dict[str, Any]) -> None:
    """Validate user has access to operations endpoints.
    
    Operations endpoints (metrics, debugging) are restricted to admins.
    In public demo mode, all users have ops access.
    
    Args:
        user: User context dictionary
        
    Raises:
        ApiError: If user lacks ops access (status 403)
        
    Example:
        >>> user = {"sub": "user-123"}
        >>> ensure_ops_access(user)  # Raises ApiError in non-demo mode
    """
    if settings.public_demo_mode or is_admin(user):
        return
    raise ApiError(
        code=ErrorCode.INVALID_REQUEST,
        message="Forbidden: enterprise ops endpoints require admin access.",
        status_code=403,
        severity=ErrorSeverity.MEDIUM,
        retryable=False,
    )


def build_app_config() -> dict[str, Any]:
    """Build application configuration dictionary for frontend.
    
    Returns configuration state that affects UI behavior:
    - App mode (production, staging, development)
    - Demo mode status
    - Authentication requirements
    - Seeding capabilities
    - Public URLs for API/app
    
    Returns:
        Configuration dictionary with:
        - app_mode: Deployment mode
        - demo_mode: Whether in demo mode
        - auth_required: Whether auth is mandatory
        - demo_seed_enabled: Whether demo data can be seeded
        - public_app_url: Public app base URL
        - public_api_url: Public API base URL
        
    Example:
        >>> config = build_app_config()
        >>> config["app_mode"]
        "production"
    """
    return {
        "app_mode": settings.app_mode.value if hasattr(settings.app_mode, "value") else str(settings.app_mode),
        "demo_mode": settings.is_demo_mode,
        "auth_required": settings.auth_required,
        "demo_seed_enabled": settings.public_demo_mode,
        "public_app_url": settings.public_app_url,
        "public_api_url": settings.public_api_url,
    }


def validate_workflow_exists(workflow: models.Workflow | None, workflow_id: int) -> None:
    """Validate that a workflow exists.
    
    Args:
        workflow: Workflow object from database (None if not found)
        workflow_id: Expected workflow ID (for error message)
        
    Raises:
        ApiError: 404 if workflow is None
        
    Example:
        >>> workflow = db.query(Workflow).filter_by(id=123).first()
        >>> validate_workflow_exists(workflow, 123)  # Raises if None
    """
    if not workflow:
        raise ApiError(
            code=ErrorCode.WORKFLOW_NOT_FOUND,
            message="Workflow not found.",
            status_code=404,
            severity=ErrorSeverity.LOW,
            retryable=False,
            details={"workflow_id": workflow_id},
        )


def validate_task_exists(task: models.Task | None, task_id: int) -> None:
    """Validate that a task exists.
    
    Args:
        task: Task object from database (None if not found)
        task_id: Expected task ID (for error message)
        
    Raises:
        ApiError: 404 if task is None
        
    Example:
        >>> task = db.query(Task).filter_by(id=456).first()
        >>> validate_task_exists(task, 456)  # Raises if None
    """
    if not task:
        raise ApiError(
            code=ErrorCode.TASK_NOT_FOUND,
            message="Task not found.",
            status_code=404,
            severity=ErrorSeverity.LOW,
            retryable=False,
            details={"task_id": task_id},
        )


def assert_workflow_owner(workflow: models.Workflow, user: dict[str, Any]) -> None:
    """Verify user owns the workflow.
    
    In demo mode or for admins, ownership is not enforced.
    For regular users, the workflow.owner must match user ID.
    
    Args:
        workflow: Workflow record
        user: User context with 'sub' field
        
    Raises:
        ApiError: 403 if user doesn't own workflow (unless admin/demo)
        
    Example:
        >>> workflow = db.query(Workflow).filter_by(id=1).first()
        >>> user = {"sub": "user-123"}
        >>> assert_workflow_owner(workflow, user)  # Raises if user != owner
    """
    if settings.public_demo_mode or is_admin(user):
        return
    if workflow.owner != user.get("sub"):
        raise ApiError(
            code=ErrorCode.INVALID_REQUEST,
            message="Forbidden: user does not own workflow.",
            status_code=403,
            severity=ErrorSeverity.MEDIUM,
            retryable=False,
            details={"workflow_id": workflow.id, "user": user.get("sub")},
        )


def get_accessible_workflows(db: Session, user: dict[str, Any]) -> list[models.Workflow]:
    """Get all workflows accessible to user.
    
    Access rules:
    - Admin/demo users: All workflows
    - Regular users: Only workflows they own
    
    Args:
        db: Database session
        user: User context with 'sub' field
        
    Returns:
        List of Workflow objects visible to user
        
    Example:
        >>> user = {"sub": "user-123"}
        >>> workflows = get_accessible_workflows(db, user)
        >>> len(workflows)
        3
    """
    if settings.public_demo_mode or is_admin(user):
        return repositories.list_workflows(db)
    return repositories.list_workflows_for_owner(db, user["sub"])


def queue_name_for_priority(priority: str) -> str:
    """Map workflow priority to Celery queue name.
    
    Queue selection affects task processing latency:
    - high_priority: Urgent/critical tasks (SLA < 30s)
    - default: Standard tasks (SLA < 5min)
    - low_cost: Background tasks (best-effort, cost optimized)
    
    Args:
        priority: Workflow priority level ('critical', 'high', 'medium', 'low')
        
    Returns:
        Queue name for Celery task routing
        
    Example:
        >>> queue_name_for_priority("critical")
        "high_priority"
        >>> queue_name_for_priority("low")
        "low_cost"
    """
    if priority in {"critical", "high"}:
        return "high_priority"
    if priority == "low":
        return "low_cost"
    return "default"


def calculate_metrics(tasks: list[models.Task]) -> dict[str, Any]:
    """Calculate workflow execution metrics.
    
    Computes basic statistics about task execution:
    - Total count by status (completed, failed, running)
    - Success rate (completed / (completed + failed))
    
    Args:
        tasks: List of Task records to analyze
        
    Returns:
        Dictionary with metrics:
        - workflows: Number of unique workflows (always 0, computed elsewhere)
        - tasks: Total task count
        - running: Tasks currently executing
        - completed: Tasks that succeeded
        - failed: Tasks that failed
        - success_rate: (completed / finished) * 100, or 100 if no finished tasks
        
    Example:
        >>> tasks = [
        ...     Task(status="completed"),
        ...     Task(status="completed"),
        ...     Task(status="failed"),
        ... ]
        >>> metrics = calculate_metrics(tasks)
        >>> metrics["success_rate"]
        66.7
    """
    completed = sum(task.status == "completed" for task in tasks)
    failed = sum(task.status == "failed" for task in tasks)
    total_finished = completed + failed
    success_rate = round((completed / total_finished) * 100, 1) if total_finished else 100.0
    return {
        "workflows": 0,
        "tasks": len(tasks),
        "running": sum(task.status == "running" for task in tasks),
        "completed": completed,
        "failed": failed,
        "success_rate": success_rate,
    }


def get_overview(db: Session, user: Dict[str, Any]) -> Dict[str, Any]:
    workflows = get_accessible_workflows(db, user)
    workflow_ids = {workflow.id for workflow in workflows}
    recent_tasks = [task for task in repositories.list_recent_tasks(db, limit=24) if task.workflow_id in workflow_ids][:8]
    all_tasks = repositories.list_all_tasks_for_workflow_ids(db, list(workflow_ids))

    metrics = calculate_metrics(all_tasks)
    metrics["workflows"] = len(workflows)

    return {
        "workflows": workflows,
        "recent_tasks": recent_tasks,
        "metrics": metrics,
    }


def record_audit_event(
    db: Session,
    *,
    actor: str,
    event: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict | None = None,
) -> models.AuditLog:
    return repositories.create_audit_log(
        db,
        actor=actor,
        event=event,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )


def create_and_queue_task(db: Session, workflow_id: int, task_payload, queue_func, *, actor: str):
    workflow = repositories.get_workflow(db, workflow_id)
    validate_workflow_exists(workflow, workflow_id)

    queue_name = queue_name_for_priority(workflow.priority)
    task_payload_full = {
        "name": task_payload.name,
        "input_data": task_payload.input,
        "agent": task_payload.agent,
        "stage": "queued",
        "status": "pending",
        "queue_name": queue_name,
    }

    task = repositories.create_task(db, workflow_id, task_payload_full)
    queue_mode = queue_func(task.id, queue_name)
    record_audit_event(
        db,
        actor=actor,
        event="task_dispatched",
        resource_type="task",
        resource_id=task.id,
        details={"workflow_id": workflow_id, "queue_name": queue_name, "queue_mode": queue_mode},
    )
    return task, queue_mode


def retry_task(db: Session, task_id: int, queue_func, *, actor: str):
    task = repositories.get_task(db, task_id)
    validate_task_exists(task, task_id)

    workflow = repositories.get_workflow(db, task.workflow_id)
    validate_workflow_exists(workflow, task.workflow_id)

    if task.status != "failed":
        raise ApiError(
            code=ErrorCode.INVALID_REQUEST,
            message="Only failed tasks can be retried.",
            status_code=409,
            severity=ErrorSeverity.LOW,
            retryable=False,
            details={"task_id": task_id, "status": task.status},
        )

    lineage_source_id = task.source_task_id or task.id
    queue_name = task.queue_name or queue_name_for_priority(workflow.priority)
    retried_task = repositories.create_task(
        db,
        task.workflow_id,
        {
            "source_task_id": lineage_source_id,
            "name": task.name,
            "agent": task.agent,
            "stage": "queued",
            "status": "pending",
            "queue_name": queue_name,
            "input_data": task.input_data,
            "retries": task.retries,
        },
    )
    queue_mode = queue_func(retried_task.id, queue_name)
    record_audit_event(
        db,
        actor=actor,
        event="task_retried",
        resource_type="task",
        resource_id=retried_task.id,
        details={"source_task_id": task.id, "workflow_id": task.workflow_id, "queue_name": queue_name, "queue_mode": queue_mode},
    )
    return retried_task, queue_mode


def create_demo_workflows(db: Session) -> List[models.Workflow]:
    workflows = [
        models.Workflow(
            name="Customer Escalation Triage",
            description="Classifies incoming incidents, scores urgency, and prepares a handoff brief for support ops.",
            owner="support-ops",
            priority="high",
            target_model="gpt-4.1",
        ),
        models.Workflow(
            name="Growth Experiment Factory",
            description="Turns campaign ideas into tested briefs with a critic pass before launch.",
            owner="growth",
            priority="medium",
            target_model="gpt-4.1-mini",
        ),
        models.Workflow(
            name="Release Readiness Review",
            description="Coordinates changelog synthesis, risk review, and launch approvals for shipping teams.",
            owner="platform",
            priority="critical",
            target_model="gpt-4.1",
        ),
    ]
    db.add_all(workflows)
    db.commit()
    for workflow in workflows:
        db.refresh(workflow)
    return workflows


def create_demo_tasks(db: Session, workflows: List[models.Workflow]) -> None:
    now = utc_now()
    tasks = [
        models.Task(
            workflow_id=workflows[0].id,
            name="Summarize billing outage",
            agent="researcher",
            status="completed",
            stage="completed",
            queue_name="high_priority",
            input_data="Urgent billing outage affecting enterprise tenants in Nairobi and London. Prepare support brief.",
            output_data='{"summary":"Incident brief created with affected tenants and response recommendation."}',
            duration_seconds=2.4,
            started_at=now,
            completed_at=now,
        ),
        models.Task(
            workflow_id=workflows[0].id,
            name="Draft executive update",
            agent="critic",
            status="failed",
            stage="failed",
            queue_name="high_priority",
            input_data="Create a concise update for executive stakeholders about the outage impact and recovery plan.",
            error_message="Primary model timed out while generating the stakeholder summary.",
            retries=1,
            started_at=now,
            completed_at=now,
        ),
        models.Task(
            workflow_id=workflows[1].id,
            name="Critique landing page experiment",
            agent="critic",
            status="running",
            stage="execution",
            queue_name="default",
            input_data="Review lifecycle email campaign experiment for activation gains and highlight blind spots.",
            started_at=now,
        ),
        models.Task(
            workflow_id=workflows[2].id,
            name="Draft go-live checklist",
            agent="planner",
            status="pending",
            stage="queued",
            queue_name="high_priority",
            input_data="Generate a release checklist for the next frontend rollout with rollback criteria.",
        ),
    ]
    db.add_all(tasks)
    db.commit()


def seed_demo_data(db: Session, *, force: bool = False, actor: str = SYSTEM_ACTOR) -> None:
    if force:
        repositories.reset_workflows_and_tasks(db)

    if repositories.list_workflows(db):
        return

    workflows = create_demo_workflows(db)
    create_demo_tasks(db, workflows)
    record_audit_event(
        db,
        actor=actor,
        event="demo_seeded" if not force else "demo_reseeded",
        resource_type="system",
        details={"workflow_count": len(workflows)},
    )


def get_ops_metrics(db: Session) -> dict[str, Any]:
    workflows = repositories.list_workflows(db)
    tasks = repositories.list_all_tasks(db)
    durations = [task.duration_seconds for task in tasks if task.duration_seconds is not None]
    failed_tasks = [task for task in tasks if task.status == "failed"]
    total_finished = sum(task.status in {"completed", "failed"} for task in tasks)
    failure_rate = round((len(failed_tasks) / total_finished) * 100, 1) if total_finished else 0.0

    workflow_failures: dict[int, dict[str, Any]] = {}
    for task in failed_tasks:
        workflow = next((item for item in workflows if item.id == task.workflow_id), None)
        if not workflow:
            continue
        bucket = workflow_failures.setdefault(
            workflow.id,
            {"workflow_id": workflow.id, "workflow_name": workflow.name, "failed_tasks": 0},
        )
        bucket["failed_tasks"] += 1

    lane_counts: dict[str, int] = {}
    for task in tasks:
        lane_counts[task.queue_name] = lane_counts.get(task.queue_name, 0) + 1

    return {
        "workflows_total": len(workflows),
        "tasks_total": len(tasks),
        "pending_tasks": sum(task.status == "pending" for task in tasks),
        "running_tasks": sum(task.status == "running" for task in tasks),
        "completed_tasks": sum(task.status == "completed" for task in tasks),
        "failed_tasks": len(failed_tasks),
        "failure_rate": failure_rate,
        "average_duration_seconds": round(mean(durations), 2) if durations else 0.0,
        "recent_failures": repositories.list_failed_tasks(db, limit=5),
        "top_failing_workflows": sorted(workflow_failures.values(), key=lambda item: item["failed_tasks"], reverse=True)[:5],
        "execution_lanes": [{"queue_name": queue_name, "tasks": count} for queue_name, count in sorted(lane_counts.items())],
    }
