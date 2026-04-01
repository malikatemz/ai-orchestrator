from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy.orm import Session

from . import models


def get_workflow(db: Session, workflow_id: int) -> Optional[models.Workflow]:
    return db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()


def list_workflows(db: Session) -> List[models.Workflow]:
    return db.query(models.Workflow).order_by(models.Workflow.created_at.desc(), models.Workflow.id.desc()).all()


def list_workflows_for_owner(db: Session, owner: str) -> List[models.Workflow]:
    return (
        db.query(models.Workflow)
        .filter(models.Workflow.owner == owner)
        .order_by(models.Workflow.created_at.desc(), models.Workflow.id.desc())
        .all()
    )


def create_workflow(db: Session, payload: dict) -> models.Workflow:
    workflow = models.Workflow(**payload)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def create_task(db: Session, workflow_id: int, payload: dict) -> models.Task:
    task = models.Task(workflow_id=workflow_id, **payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[models.Task]:
    return db.query(models.Task).filter(models.Task.id == task_id).first()


def list_tasks(db: Session, workflow_id: int) -> List[models.Task]:
    return db.query(models.Task).filter(models.Task.workflow_id == workflow_id).order_by(models.Task.created_at.desc(), models.Task.id.desc()).all()


def list_recent_tasks(db: Session, limit: int = 8) -> List[models.Task]:
    return db.query(models.Task).order_by(models.Task.created_at.desc(), models.Task.id.desc()).limit(limit).all()


def list_all_tasks(db: Session) -> List[models.Task]:
    return db.query(models.Task).all()


def list_all_tasks_for_workflow_ids(db: Session, workflow_ids: list[int]) -> List[models.Task]:
    if not workflow_ids:
        return []
    return db.query(models.Task).filter(models.Task.workflow_id.in_(workflow_ids)).all()


def list_failed_tasks(db: Session, limit: int = 5) -> List[models.Task]:
    return (
        db.query(models.Task)
        .filter(models.Task.status == "failed")
        .order_by(models.Task.completed_at.desc(), models.Task.id.desc())
        .limit(limit)
        .all()
    )


def reset_workflows_and_tasks(db: Session) -> None:
    db.query(models.Task).delete()
    db.query(models.Workflow).delete()
    db.commit()


def create_audit_log(
    db: Session,
    *,
    actor: str,
    event: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict | None = None,
) -> models.AuditLog:
    entry = models.AuditLog(
        actor=actor,
        event=event,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=json.dumps(details or {}),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(db: Session, limit: int = 50) -> List[models.AuditLog]:
    return db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc(), models.AuditLog.id.desc()).limit(limit).all()
