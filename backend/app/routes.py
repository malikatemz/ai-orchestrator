from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import schemas
from .auth import get_current_user
from .database import get_db
from .error_handling import ApiError, ErrorCode, ErrorSeverity
from .observability import configure_logging, log_event
from .presenters import model_to_dict, serialize_overview, serialize_task, serialize_workflow
from .services import assert_workflow_owner, get_accessible_workflows, get_overview, create_and_queue_task, is_admin, validate_workflow_exists
from .repositories import create_workflow, get_workflow, list_tasks
from .worker import queue_task

logger = configure_logging()
router = APIRouter()
API_ROOT_PAYLOAD = {"message": "AI Orchestrator API", "docs": "/docs", "health": "/health", "overview": "/overview"}


def get_and_validate_workflow(db: Session, workflow_id: int, current_user):
    """Helper to get, validate existence, and assert ownership of a workflow."""
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
    payload["owner"] = current_user["sub"]
    created = create_workflow(db, payload)
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
    task_item, queue_mode = create_and_queue_task(db, workflow_id, task, queue_task)
    log_event(logger=logger, level="info", event="task_queued", workflow_id=workflow_id, task_id=task_item.id, queue_mode=queue_mode, request_id=request.state.request_id)
    return serialize_task(task_item)


@router.post("/seed-demo", response_model=schemas.OverviewResponse)
async def reseed_demo(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from .services import seed_demo_data

    if not is_admin(current_user):
        raise ApiError(
            code=ErrorCode.INVALID_REQUEST,
            message="Forbidden: only admin can reseed demo data.",
            status_code=403,
            severity=ErrorSeverity.HIGH,
            retryable=False,
        )

    seed_demo_data(db)
    return serialize_overview(get_overview(db, current_user))
