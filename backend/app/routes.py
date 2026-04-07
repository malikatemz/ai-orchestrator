from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import schemas
from .api_auth import get_current_user
from .database import get_db
from .error_handling import ApiError, ErrorCode, ErrorSeverity
from .observability import configure_logging, log_event
from .presenters import model_to_dict, model_to_output, serialize_audit_log, serialize_ops_metrics, serialize_overview, serialize_task, serialize_workflow
from .repositories import create_workflow, get_workflow, get_task, list_audit_logs, list_tasks
from .services import (
    SYSTEM_ACTOR,
    assert_workflow_owner,
    build_app_config,
    can_manage_demo,
    create_and_queue_task,
    ensure_ops_access,
    get_accessible_workflows,
    get_ops_metrics,
    get_overview,
    is_admin,
    record_audit_event,
    retry_task,
    seed_demo_data,
    validate_task_exists,
    validate_workflow_exists,
)
from .time_utils import utc_now
from .worker import queue_task

logger = configure_logging()
router = APIRouter()
API_ROOT_PAYLOAD = {"message": "AI Orchestrator API", "docs": "/docs", "health": "/health", "overview": "/overview"}


def get_and_validate_workflow(db: Session, workflow_id: int, current_user):
    """Helper to fetch and authorize workflow access.
    
    Args:
        db: Database session
        workflow_id: Workflow ID to fetch
        current_user: Current authenticated user
    
    Returns:
        Workflow model if user has access
    
    Raises:
        ApiError: If workflow not found or access denied
    """
    workflow = get_workflow(db, workflow_id)
    validate_workflow_exists(workflow, workflow_id)
    assert_workflow_owner(workflow, current_user)
    return workflow


@router.get("/")
async def root() -> dict[str, Any]:
    """API root endpoint with navigation links.
    
    Returns:
        Welcome message and links to key endpoints
    
    Status Codes:
        200: Success
    
    Example:
        >>> response = client.get("/")
        >>> response.json()
        {
            "message": "AI Orchestrator API",
            "docs": "/docs",
            "health": "/health",
            "overview": "/overview"
        }
    """
    return API_ROOT_PAYLOAD


@router.get("/health", response_model=schemas.HealthResponse)
async def health() -> schemas.HealthResponse:
    """Health check endpoint for monitoring.
    
    Returns:
        System health status including database and queue connectivity
    
    Status Codes:
        200: All systems operational
    
    Example:
        >>> response = client.get("/health")
        >>> response.json()
        {
            "status": "ok",
            "database": "connected",
            "queue_mode": "celery-with-inline-fallback",
            "timestamp": "2026-04-07T07:11:12Z"
        }
    """
    return schemas.HealthResponse(status="ok", database="connected", queue_mode="celery-with-inline-fallback", timestamp=utc_now())


@router.get("/app-config", response_model=schemas.AppConfigResponse)
async def app_config() -> schemas.AppConfigResponse:
    """Get application configuration and feature flags.
    
    Returns:
        App configuration including feature flags and deployment settings
    
    Status Codes:
        200: Success
    
    Example:
        >>> response = client.get("/app-config")
        >>> response.json()
        {
            "deployment_mode": "production",
            "queue_engine": "celery",
            "features": {...}
        }
    """
    return schemas.AppConfigResponse(**build_app_config())


@router.get("/diagnostics/runtime")
async def diagnostics_runtime() -> dict[str, Any]:
    """Get runtime environment fingerprint for debugging.
    
    Returns:
        Runtime information (Python version, platform, environment)
        Useful for debugging deployment-specific issues
    
    Status Codes:
        200: Success
    
    Example:
        >>> response = client.get("/diagnostics/runtime")
        >>> response.json()
        {
            "runtime": {
                "python_version": "3.11.4",
                "platform": "Linux",
                ...
            }
        }
    """
    from .diagnostics import runtime_fingerprint

    return {"runtime": runtime_fingerprint()}


@router.get("/overview", response_model=schemas.OverviewResponse)
async def overview(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.OverviewResponse:
    """Get personalized user overview with recent activity.
    
    Requires authentication. Returns user's accessible workflows, recent tasks, and metrics.
    
    Args:
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        OverviewResponse with workflows, recent tasks, and stats
    
    Status Codes:
        200: Success
        401: User not authenticated
    
    Example:
        >>> response = client.get(
        ...     "/overview",
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> response.json()
        {
            "workflows": [...],
            "recent_tasks": [...],
            "total_tasks": 42,
            "success_rate": 0.98
        }
    """
    return serialize_overview(get_overview(db, current_user))


@router.get("/workflows", response_model=list[schemas.WorkflowSummary])
async def workflows(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[schemas.WorkflowSummary]:
    """List all workflows accessible to the current user.
    
    Requires authentication. Returns only workflows the user owns or has been granted access to.
    
    Args:
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        List of WorkflowSummary objects
    
    Status Codes:
        200: Success
        401: User not authenticated
    
    Permission:
        Requires: workflow:read on at least one workflow
    
    Example:
        >>> response = client.get(
        ...     "/workflows",
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> workflows = response.json()
        >>> len(workflows)
        5
    """
    return [serialize_workflow(wf) for wf in get_accessible_workflows(db, current_user)]


@router.get("/workflows/{workflow_id}", response_model=schemas.WorkflowDetail)
async def workflow_detail(workflow_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.WorkflowDetail:
    """Get detailed information for a specific workflow.
    
    Requires authentication and access to the workflow. Returns workflow definition plus
    all associated tasks with their execution status.
    
    Args:
        workflow_id: Target workflow ID (path parameter)
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        WorkflowDetail with full workflow definition and task history
    
    Status Codes:
        200: Success
        401: User not authenticated
        403: User lacks access to workflow
        404: Workflow not found
    
    Permission:
        Requires: workflow:read on target workflow
    
    Example:
        >>> response = client.get(
        ...     "/workflows/123",
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> workflow = response.json()
        >>> workflow["name"]
        "Email Summarizer"
        >>> len(workflow["tasks"])
        12
    """
    workflow = get_and_validate_workflow(db, workflow_id, current_user)
    summary = serialize_workflow(workflow)
    return schemas.WorkflowDetail(**model_to_output(summary), tasks=[serialize_task(task) for task in workflow.tasks])


@router.post("/workflows", response_model=schemas.WorkflowSummary, status_code=201)
async def create_workflow_v1(workflow: schemas.WorkflowCreate, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.WorkflowSummary:
    """Create a new workflow.
    
    Requires authentication. Creates a new workflow template that can be executed multiple times.
    User becomes the owner unless they have demo-mode privileges (then can specify owner).
    
    Args:
        workflow: Request body with workflow definition
        request: FastAPI Request object (for logging)
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        Created WorkflowSummary with new workflow ID
    
    Status Codes:
        201: Workflow created successfully
        400: Invalid workflow definition (missing required fields)
        401: User not authenticated
        422: Validation error in request body
    
    Permission:
        Requires: workflow:create permission
        Owner defaults to current_user unless user has demo privileges
    
    Example:
        >>> request_body = {
        ...     "name": "Email Analyzer",
        ...     "description": "Analyze incoming emails",
        ...     "priority": "high",
        ...     "target_model": "gpt-4"
        ... }
        >>> response = client.post(
        ...     "/workflows",
        ...     json=request_body,
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> response.status_code
        201
        >>> workflow = response.json()
        >>> workflow["id"]
        123
    """
    payload = model_to_dict(workflow)
    payload["owner"] = payload["owner"] if can_manage_demo(current_user) or is_admin(current_user) else current_user["sub"]
    created = create_workflow(db, payload)
    record_audit_event(
        db,
        actor=current_user["sub"],
        event="workflow_created",
        resource_type="workflow",
        resource_id=created.id,
        details={"priority": created.priority, "target_model": created.target_model},
    )
    log_event(logger=logger, level="info", event="workflow_created", workflow_id=created.id, request_id=request.state.request_id, owner=created.owner, priority=created.priority)
    return serialize_workflow(created)


@router.get("/workflows/{workflow_id}/tasks", response_model=list[schemas.TaskResponse])
async def tasks(workflow_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[schemas.TaskResponse]:
    """List all tasks for a workflow.
    
    Requires authentication and access to the workflow. Returns all tasks executed under
    the workflow in creation order.
    
    Args:
        workflow_id: Target workflow ID (path parameter)
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        List of TaskResponse objects
    
    Status Codes:
        200: Success
        401: User not authenticated
        403: User lacks access to workflow
        404: Workflow not found
    
    Permission:
        Requires: workflow:read on target workflow
    
    Example:
        >>> response = client.get(
        ...     "/workflows/123/tasks",
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> tasks = response.json()
        >>> len(tasks)
        42
        >>> tasks[0]["status"]
        "succeeded"
    """
    get_and_validate_workflow(db, workflow_id, current_user)
    db_tasks = list_tasks(db, workflow_id)
    return [serialize_task(task) for task in db_tasks]


@router.post("/workflows/{workflow_id}/tasks", response_model=schemas.TaskResponse, status_code=202)
async def create_task_v1(workflow_id: int, task: schemas.TaskCreate, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.TaskResponse:
    """Create and queue a new task for a workflow.
    
    Requires authentication and edit access to the workflow. Validates input, creates Task record,
    queues in Celery (with fallback to inline execution), and returns immediately with task ID
    and status='queued'.
    
    Args:
        workflow_id: Target workflow ID (path parameter)
        task: Request body with task input data
        request: FastAPI Request object (for logging)
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        TaskResponse with ID, status='queued', and metadata
    
    Status Codes:
        202: Task queued for async execution (request accepted, processing later)
        400: Invalid task data (missing fields, too large, etc.)
        401: User not authenticated
        403: User lacks edit permission on workflow
        404: Workflow not found
        422: Validation error in request body
    
    Permission:
        Requires: workflow:edit on target workflow
    
    Queueing:
        - High-priority tasks: Queued to high_priority Celery queue
        - Low-cost mode: Queued to low_cost queue (limited provider pool)
        - Default: Queued to default queue
        - Fallback: If Celery unavailable, executes inline synchronously
    
    Example:
        >>> task_input = {"prompt": "Summarize this email..."}
        >>> response = client.post(
        ...     "/workflows/123/tasks",
        ...     json=task_input,
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> response.status_code
        202
        >>> task = response.json()
        >>> task["id"]
        42
        >>> task["status"]
        "queued"
    """
    get_and_validate_workflow(db, workflow_id, current_user)
    task_item, queue_mode = create_and_queue_task(db, workflow_id, task, queue_task, actor=current_user["sub"])
    log_event(logger=logger, level="info", event="task_queued", workflow_id=workflow_id, task_id=task_item.id, queue_mode=queue_mode, request_id=request.state.request_id, queue_name=task_item.queue_name)
    return serialize_task(task_item)


@router.post("/tasks/{task_id}/retry", response_model=schemas.TaskResponse, status_code=202)
async def retry_task_v1(task_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.TaskResponse:
    """Retry a previously failed task.
    
    Requires authentication and access to the task's workflow. Creates a new Task record
    linked to the original (source_task_id) and queues it. Preserves input data from original
    task. Useful for transient failures (timeouts, rate limits).
    
    Args:
        task_id: Original task ID to retry (path parameter)
        request: FastAPI Request object (for logging)
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        TaskResponse for the new retry task (status='queued')
    
    Status Codes:
        202: Task queued for retry
        401: User not authenticated
        403: User lacks access to workflow
        404: Task not found
        409: Task cannot be retried (e.g., successful task, timeout retry limit exceeded)
    
    Permission:
        Requires: workflow:edit on task's workflow
    
    Retry Logic:
        - Increments retries counter
        - Copies input_data from original task
        - Respects max retry limit (typically 3 attempts)
        - Creates audit log entry with source_task_id reference
    
    Example:
        >>> response = client.post(
        ...     "/tasks/42/retry",
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> response.status_code
        202
        >>> new_task = response.json()
        >>> new_task["id"]
        43
        >>> new_task["status"]
        "queued"
    """
    original_task = get_task(db, task_id)
    validate_task_exists(original_task, task_id)
    workflow = get_and_validate_workflow(db, original_task.workflow_id, current_user)
    assert_workflow_owner(workflow, current_user)
    task_item, queue_mode = retry_task(db, task_id, queue_task, actor=current_user["sub"])
    log_event(
        logger=logger,
        level="info",
        event="task_retried",
        workflow_id=task_item.workflow_id,
        task_id=task_item.id,
        source_task_id=task_id,
        queue_mode=queue_mode,
        queue_name=task_item.queue_name,
        request_id=request.state.request_id,
    )
    return serialize_task(task_item)


@router.post("/seed-demo", response_model=schemas.OverviewResponse)
async def reseed_demo(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.OverviewResponse:
    """Reseed demo data (admin/demo-mode only).
    
    Requires special permission. Wipes and recreates all demo workflows and tasks. Useful for
    resetting environment to clean state for demos, testing, or customer onboarding.
    
    Args:
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        Updated OverviewResponse with fresh demo data
    
    Status Codes:
        200: Demo data reseeded successfully
        401: User not authenticated
        403: Forbidden - only demo mode or admin users can reseed
    
    Permission:
        Requires: Demo mode OR platform admin role
    
    Effects:
        - Deletes all existing demo workflows and tasks
        - Creates fresh set of example workflows
        - Queues initial demo tasks
        - Records audit log entry
    
    Example:
        >>> response = client.post(
        ...     "/seed-demo",
        ...     headers={"Authorization": "Bearer admin_token"}
        ... )
        >>> response.status_code
        200
        >>> overview = response.json()
        >>> len(overview["workflows"])
        5  # Fresh demo workflows
    """
    if not can_manage_demo(current_user):
        raise ApiError(
            code=ErrorCode.INVALID_REQUEST,
            message="Forbidden: only demo mode or admin users can reseed demo data.",
            status_code=403,
            severity=ErrorSeverity.HIGH,
            retryable=False,
        )

    seed_demo_data(db, force=True, actor=current_user.get("sub", SYSTEM_ACTOR))
    return serialize_overview(get_overview(db, current_user))


@router.get("/ops/metrics", response_model=schemas.OpsMetricsResponse)
async def ops_metrics(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.OpsMetricsResponse:
    """Get operations metrics and system health (ops/admin only).
    
    Requires admin privilege. Returns detailed system metrics including task success rates,
    queue depths, provider performance, billing summaries, and alerts.
    
    Args:
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        OpsMetricsResponse with comprehensive system metrics
    
    Status Codes:
        200: Success
        401: User not authenticated
        403: User lacks admin privilege
    
    Permission:
        Requires: platform admin or ops role
    
    Metrics Included:
        - Task execution: success rate, avg latency, failure breakdown
        - Queue health: depth, processing rate, backed-up queues
        - Provider performance: availability, latency, error rates
        - Billing: daily spend, top spenders, usage trends
        - System: uptime, database health, cache hit rate
    
    Example:
        >>> response = client.get(
        ...     "/ops/metrics",
        ...     headers={"Authorization": "Bearer admin_token"}
        ... )
        >>> response.status_code
        200
        >>> metrics = response.json()
        >>> metrics["task_success_rate"]
        0.987
        >>> metrics["queue_depth"]
        42
    """
    ensure_ops_access(current_user)
    return serialize_ops_metrics(get_ops_metrics(db))


@router.get("/ops/audit-logs", response_model=list[schemas.AuditLogResponse])
async def ops_audit_logs(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[schemas.AuditLogResponse]:
    """Get audit log entries (ops/admin only).
    
    Requires admin privilege. Returns most recent audit log entries for security review,
    compliance reporting, and incident investigation.
    
    Args:
        current_user: Authenticated user (auto-injected)
        db: Database session (auto-injected)
    
    Returns:
        List of most recent AuditLogResponse objects (max 50)
    
    Status Codes:
        200: Success
        401: User not authenticated
        403: User lacks admin privilege
    
    Permission:
        Requires: platform admin or ops role
    
    Entries Returned:
        - Most recent 50 audit log entries
        - Sorted by creation time (newest first)
        - Includes all event types: user actions, resource changes, auth events, errors
    
    Use Cases:
        - Security review: Who accessed what and when
        - Compliance: Audit trail for regulatory requirements
        - Incident investigation: Trace of events leading to issue
        - User activity: Recent actions for a specific user/resource
    
    Example:
        >>> response = client.get(
        ...     "/ops/audit-logs",
        ...     headers={"Authorization": "Bearer admin_token"}
        ... )
        >>> response.status_code
        200
        >>> logs = response.json()
        >>> len(logs)
        50  # Most recent entries
        >>> logs[0]["event"]
        "workflow_created"
    """
    ensure_ops_access(current_user)
    return [serialize_audit_log(entry) for entry in list_audit_logs(db, limit=50)]
