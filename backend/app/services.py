from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from . import models, repositories
from .error_handling import ApiError, ErrorCode, ErrorSeverity


def is_admin(user: Dict[str, Any]) -> bool:
    """Check if the user has admin privileges."""
    return user.get("sub") == "admin" or "orchestrator:admin" in user.get("scopes", [])


def validate_workflow_exists(workflow, workflow_id: int) -> None:
    """Raise an error if the workflow does not exist."""
    if not workflow:
        raise ApiError(
            code=ErrorCode.WORKFLOW_NOT_FOUND,
            message="Workflow not found.",
            status_code=404,
            severity=ErrorSeverity.LOW,
            retryable=False,
            details={"workflow_id": workflow_id},
        )


def assert_workflow_owner(workflow: models.Workflow, user: Dict[str, Any]) -> None:
    """Assert that the user owns the workflow or is admin."""
    if is_admin(user):
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


def get_accessible_workflows(db: Session, user: Dict[str, Any]) -> List[models.Workflow]:
    """Get workflows accessible to the user (all for admin, owned for others)."""
    if is_admin(user):
        return repositories.list_workflows(db)
    return repositories.list_workflows_for_owner(db, user["sub"])


def calculate_metrics(tasks: List[models.Task]) -> Dict[str, Any]:
    """Calculate overview metrics from tasks."""
    completed = sum(task.status == "completed" for task in tasks)
    failed = sum(task.status == "failed" for task in tasks)
    total_finished = completed + failed
    success_rate = round((completed / total_finished) * 100, 1) if total_finished else 100.0
    return {
        "workflows": 0,  # Will be set in get_overview
        "tasks": len(tasks),
        "running": sum(task.status == "running" for task in tasks),
        "completed": completed,
        "failed": failed,
        "success_rate": success_rate,
    }


def get_overview(db: Session, user: Dict[str, Any]) -> Dict[str, Any]:
    """Get overview data for the user."""
    workflows = get_accessible_workflows(db, user)
    workflow_ids = {workflow.id for workflow in workflows}
    recent_tasks = [task for task in repositories.list_recent_tasks(db, limit=16) if task.workflow_id in workflow_ids][:8]
    all_tasks = repositories.list_all_tasks_for_workflow_ids(db, list(workflow_ids))

    metrics = calculate_metrics(all_tasks)
    metrics["workflows"] = len(workflows)

    return {
        "workflows": workflows,
        "recent_tasks": recent_tasks,
        "metrics": metrics,
    }


def create_and_queue_task(db: Session, workflow_id: int, task_payload, queue_func):
    """Create a task and queue it for execution."""
    workflow = repositories.get_workflow(db, workflow_id)
    validate_workflow_exists(workflow, workflow_id)

    task_payload_full = {
        "name": task_payload.name,
        "input_data": task_payload.input,
        "agent": task_payload.agent,
        "stage": "queued",
        "status": "pending",
    }

    task = repositories.create_task(db, workflow_id, task_payload_full)
    queue_mode = queue_func(task.id)
    return task, queue_mode


def create_demo_workflows(db: Session) -> List[models.Workflow]:
    """Create demo workflows."""
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
    return workflows


def create_demo_tasks(db: Session, workflows: List[models.Workflow]) -> None:
    """Create demo tasks."""
    tasks = [
        models.Task(
            workflow_id=workflows[0].id,
            name="Summarize billing outage",
            agent="researcher",
            status="completed",
            stage="completed",
            input_data="Urgent billing outage affecting enterprise tenants in Nairobi and London. Prepare support brief.",
            output_data='{"summary":"Incident brief created with affected tenants and response recommendation."}',
            duration_seconds=2.4,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        ),
        models.Task(
            workflow_id=workflows[1].id,
            name="Critique landing page experiment",
            agent="critic",
            status="running",
            stage="execution",
            input_data="Review lifecycle email campaign experiment for activation gains and highlight blind spots.",
            started_at=datetime.utcnow(),
        ),
        models.Task(
            workflow_id=workflows[2].id,
            name="Draft go-live checklist",
            agent="planner",
            status="pending",
            stage="queued",
            input_data="Generate a release checklist for the next frontend rollout with rollback criteria.",
        ),
    ]
    db.add_all(tasks)
    db.commit()


def seed_demo_data(db: Session) -> None:
    """Seed the database with demo data if empty."""
    if repositories.list_workflows(db):
        return

    workflows = create_demo_workflows(db)
    create_demo_tasks(db, workflows)
