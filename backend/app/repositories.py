from typing import List, Optional

from sqlalchemy.orm import Session

from . import models


def get_workflow(db: Session, workflow_id: int) -> Optional[models.Workflow]:
    """Retrieve a workflow by ID."""
    return db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()


def list_workflows(db: Session) -> List[models.Workflow]:
    """List all workflows ordered by creation date descending."""
    return db.query(models.Workflow).order_by(models.Workflow.created_at.desc()).all()


def list_workflows_for_owner(db: Session, owner: str) -> List[models.Workflow]:
    """List workflows for a specific owner ordered by creation date descending."""
    return (
        db.query(models.Workflow)
        .filter(models.Workflow.owner == owner)
        .order_by(models.Workflow.created_at.desc())
        .all()
    )


def create_workflow(db: Session, payload: dict) -> models.Workflow:
    """Create a new workflow from payload."""
    workflow = models.Workflow(**payload)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def create_task(db: Session, workflow_id: int, payload: dict) -> models.Task:
    """Create a new task for a workflow."""
    task = models.Task(workflow_id=workflow_id, **payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, workflow_id: int) -> List[models.Task]:
    """List tasks for a workflow ordered by creation date descending."""
    return db.query(models.Task).filter(models.Task.workflow_id == workflow_id).order_by(models.Task.created_at.desc()).all()


def list_recent_tasks(db: Session, limit: int = 8) -> List[models.Task]:
    """List recent tasks ordered by creation date descending."""
    return db.query(models.Task).order_by(models.Task.created_at.desc()).limit(limit).all()


def list_all_tasks(db: Session) -> List[models.Task]:
    """List all tasks."""
    return db.query(models.Task).all()


def list_all_tasks_for_workflow_ids(db: Session, workflow_ids: list[int]):
    if not workflow_ids:
        return []
    return db.query(models.Task).filter(models.Task.workflow_id.in_(workflow_ids)).all()
