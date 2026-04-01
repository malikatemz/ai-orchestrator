from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import schemas
from .auth import get_current_user
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
from .worker import queue_task

logger = configure_logging()
router = APIRouter()
API_ROOT_PAYLOAD = {"message": "AI Orchestrator API", "docs": "/docs", "health": "/health", "overview": "/overview"}


def get_and_validate_workflow(db: Session, workflow_id: int, current_user):
    workflow = get_workflow(db, workflow_id)
    validate_workflow_exists(workflow, workflow_id)
    assert_workflow_owner(workflow, current_user)
    return workflow


@router.get("/")
async def root():
    return API_ROOT_PAYLOAD


@router.get("/health", response_model=schemas.HealthResponse)
async def health():
    return schemas.HealthResponse(status="ok", database="connected", queue_mode="celery-with-inline-fallback", timestamp=datetime.utcnow())


@router.get("/app-config", response_model=schemas.AppConfigResponse)
async def app_config():
    return schemas.AppConfigResponse(**build_app_config())


@router.get("/diagnostics/runtime")
async def diagnostics_runtime():
    from .diagnostics import runtime_fingerprint

    return {"runtime": runtime_fingerprint()}


@router.get("/overview", response_model=schemas.OverviewResponse)
async def overview(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_overview(get_overview(db, current_user))


@router.get("/workflows", response_model=List[schemas.WorkflowSummary])
async def workflows(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return [serialize_workflow(wf) for wf in get_accessible_workflows(db, current_user)]


@router.get("/workflows/{workflow_id}", response_model=schemas.WorkflowDetail)
async def workflow_detail(workflow_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    workflow = get_and_validate_workflow(db, workflow_id, current_user)
    summary = serialize_workflow(workflow)
    return schemas.WorkflowDetail(**model_to_output(summary), tasks=[serialize_task(task) for task in workflow.tasks])


@router.post("/workflows", response_model=schemas.WorkflowSummary, status_code=201)
async def create_workflow_v1(workflow: schemas.WorkflowCreate, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
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


@router.get("/workflows/{workflow_id}/tasks", response_model=List[schemas.TaskResponse])
async def tasks(workflow_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    get_and_validate_workflow(db, workflow_id, current_user)
    db_tasks = list_tasks(db, workflow_id)
    return [serialize_task(task) for task in db_tasks]


@router.post("/workflows/{workflow_id}/tasks", response_model=schemas.TaskResponse, status_code=202)
async def create_task_v1(workflow_id: int, task: schemas.TaskCreate, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    get_and_validate_workflow(db, workflow_id, current_user)
    task_item, queue_mode = create_and_queue_task(db, workflow_id, task, queue_task, actor=current_user["sub"])
    log_event(logger=logger, level="info", event="task_queued", workflow_id=workflow_id, task_id=task_item.id, queue_mode=queue_mode, request_id=request.state.request_id, queue_name=task_item.queue_name)
    return serialize_task(task_item)


@router.post("/tasks/{task_id}/retry", response_model=schemas.TaskResponse, status_code=202)
async def retry_task_v1(task_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
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
async def reseed_demo(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
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
async def ops_metrics(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_ops_access(current_user)
    return serialize_ops_metrics(get_ops_metrics(db))


@router.get("/ops/audit-logs", response_model=List[schemas.AuditLogResponse])
async def ops_audit_logs(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_ops_access(current_user)
    return [serialize_audit_log(entry) for entry in list_audit_logs(db, limit=50)]
