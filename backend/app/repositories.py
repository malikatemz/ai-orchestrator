from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from . import models


def get_workflow(db: Session, workflow_id: int) -> models.Workflow | None:
    """Fetch a workflow by ID.
    
    Simple lookup query, no filtering or authorization checks.
    Consumers should validate ownership/permissions before returning to user.
    
    Args:
        db: SQLAlchemy database session
        workflow_id: Workflow ID to fetch
    
    Returns:
        Workflow model if found, None otherwise
    
    Note:
        Returns None if not found (no exception). Callers should handle None explicitly.
    
    Example:
        >>> workflow = get_workflow(db, 42)
        >>> if workflow:
        ...     print(workflow.name)
        ... else:
        ...     print("Not found")
    """
    return db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()


def list_workflows(db: Session) -> list[models.Workflow]:
    """List all workflows ordered by creation date (newest first).
    
    No filtering or access control. Should only be called in admin contexts.
    For user-accessible workflows, use services.get_accessible_workflows() instead.
    
    Args:
        db: SQLAlchemy database session
    
    Returns:
        List of all Workflow models (may be empty)
    
    Sorting:
        Primary: created_at DESC (newest first)
        Secondary: id DESC (stable ordering for same-timestamp entries)
    
    Example:
        >>> workflows = list_workflows(db)
        >>> recent = workflows[0]
    """
    return db.query(models.Workflow).order_by(models.Workflow.created_at.desc(), models.Workflow.id.desc()).all()


def list_workflows_for_owner(db: Session, owner: str) -> list[models.Workflow]:
    """List all workflows owned by a specific user.
    
    Filters by owner field. Useful for "my workflows" queries.
    Returns all workflows regardless of status (active, archived, etc.).
    
    Args:
        db: SQLAlchemy database session
        owner: User ID of workflow owner
    
    Returns:
        List of Workflow models owned by user (may be empty)
    
    Sorting:
        Primary: created_at DESC (newest first)
        Secondary: id DESC (stable ordering)
    
    Example:
        >>> user_workflows = list_workflows_for_owner(db, "user-123")
        >>> for wf in user_workflows:
        ...     print(wf.name)
    """
    return (
        db.query(models.Workflow)
        .filter(models.Workflow.owner == owner)
        .order_by(models.Workflow.created_at.desc(), models.Workflow.id.desc())
        .all()
    )


def create_workflow(db: Session, payload: dict[str, Any]) -> models.Workflow:
    """Create a new workflow in the database.
    
    Inserts and commits immediately. Payload should be validated by caller.
    
    Args:
        db: SQLAlchemy database session
        payload: Dictionary of workflow attributes
            Required keys: name, description, owner, priority, target_model
            See models.Workflow for full attribute list
    
    Returns:
        Created Workflow model with auto-generated ID
    
    Raises:
        SQLAlchemy exceptions: If payload invalid or constraint violated
    
    Example:
        >>> payload = {
        ...     "name": "Email Summarizer",
        ...     "description": "Summarize incoming emails",
        ...     "owner": "user-123",
        ...     "priority": "high",
        ...     "target_model": "gpt-4"
        ... }
        >>> workflow = create_workflow(db, payload)
        >>> print(workflow.id)  # Auto-assigned ID
        42
    """
    workflow = models.Workflow(**payload)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def create_task(db: Session, workflow_id: int, payload: dict[str, Any]) -> models.Task:
    """Create a new task in the database.
    
    Inserts and commits immediately. Payload should be validated by caller.
    Links task to workflow via workflow_id.
    
    Args:
        db: SQLAlchemy database session
        workflow_id: Parent workflow ID (not nullable)
        payload: Dictionary of task attributes
            Common keys: name, agent, status, input_data, queue_name
            See models.Task for full attribute list
    
    Returns:
        Created Task model with auto-generated ID
    
    Raises:
        SQLAlchemy exceptions: If payload invalid or workflow_id invalid
    
    Example:
        >>> payload = {
        ...     "name": "Analyze content",
        ...     "agent": "executor",
        ...     "status": "pending",
        ...     "input_data": '{"content": "..."}',
        ...     "queue_name": "default"
        ... }
        >>> task = create_task(db, workflow_id=42, payload=payload)
        >>> print(task.id)  # Auto-assigned ID
        123
    """
    task = models.Task(workflow_id=workflow_id, **payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> models.Task | None:
    """Fetch a task by ID.
    
    Simple lookup query, no filtering or validation.
    Consumers should validate ownership before returning to user.
    
    Args:
        db: SQLAlchemy database session
        task_id: Task ID to fetch
    
    Returns:
        Task model if found, None otherwise
    
    Note:
        Returns None if not found (no exception). Callers should handle None explicitly.
    
    Example:
        >>> task = get_task(db, 123)
        >>> if task:
        ...     print(task.status)
        ... else:
        ...     print("Not found")
    """
    return db.query(models.Task).filter(models.Task.id == task_id).first()


def list_tasks(db: Session, workflow_id: int) -> list[models.Task]:
    """List all tasks for a specific workflow.
    
    Filters by workflow_id. Returns all tasks (all statuses).
    
    Args:
        db: SQLAlchemy database session
        workflow_id: Workflow ID to list tasks for
    
    Returns:
        List of Task models for workflow (may be empty)
    
    Sorting:
        Primary: created_at DESC (newest first)
        Secondary: id DESC (stable ordering)
    
    Example:
        >>> tasks = list_tasks(db, workflow_id=42)
        >>> for task in tasks:
        ...     print(f"{task.name}: {task.status}")
    """
    return db.query(models.Task).filter(models.Task.workflow_id == workflow_id).order_by(models.Task.created_at.desc(), models.Task.id.desc()).all()


def list_recent_tasks(db: Session, limit: int = 8) -> list[models.Task]:
    """List most recent tasks across all workflows.
    
    Useful for dashboards and overview pages. No filtering by workflow or owner.
    
    Args:
        db: SQLAlchemy database session
        limit: Maximum number of tasks to return (default 8)
    
    Returns:
        List of Task models (up to limit, ordered by creation time)
    
    Sorting:
        Primary: created_at DESC (newest first)
        Secondary: id DESC (stable ordering)
    
    Example:
        >>> recent = list_recent_tasks(db, limit=10)
        >>> for task in recent:
        ...     print(f"{task.created_at}: {task.name}")
    """
    return db.query(models.Task).order_by(models.Task.created_at.desc(), models.Task.id.desc()).limit(limit).all()


def list_all_tasks(db: Session) -> list[models.Task]:
    """List all tasks in the system.
    
    No filtering or limits. Use with caution in large datasets.
    For analytics, consider using direct SQL or specialized queries.
    
    Args:
        db: SQLAlchemy database session
    
    Returns:
        List of all Task models (may be very large)
    
    Warning:
        Do not call this without a limit in production environments
        with large task histories. Use list_recent_tasks() instead.
    
    Example:
        >>> all_tasks = list_all_tasks(db)
        >>> success_count = sum(1 for t in all_tasks if t.status == "succeeded")
    """
    return db.query(models.Task).all()


def list_all_tasks_for_workflow_ids(db: Session, workflow_ids: list[int]) -> list[models.Task]:
    """List tasks for multiple workflows in a single query.
    
    Useful for bulk operations. Returns empty list if workflow_ids is empty.
    
    Args:
        db: SQLAlchemy database session
        workflow_ids: List of workflow IDs to fetch tasks for
    
    Returns:
        List of Task models from specified workflows (may be empty)
    
    Note:
        Returns empty list (not exception) if workflow_ids is empty
    
    Example:
        >>> workflow_ids = [1, 2, 3]
        >>> tasks = list_all_tasks_for_workflow_ids(db, workflow_ids)
        >>> for task in tasks:
        ...     print(f"Workflow {task.workflow_id}: {task.name}")
    """
    if not workflow_ids:
        return []
    return db.query(models.Task).filter(models.Task.workflow_id.in_(workflow_ids)).all()


def list_failed_tasks(db: Session, limit: int = 5) -> list[models.Task]:
    """List most recent failed tasks.
    
    Useful for error dashboards and troubleshooting.
    
    Args:
        db: SQLAlchemy database session
        limit: Maximum failed tasks to return (default 5)
    
    Returns:
        List of Task models with status='failed' (up to limit)
    
    Sorting:
        Primary: completed_at DESC (most recently failed first)
        Secondary: id DESC (stable ordering)
    
    Example:
        >>> failed = list_failed_tasks(db, limit=10)
        >>> for task in failed:
        ...     print(f"{task.completed_at}: {task.error_message}")
    """
    return (
        db.query(models.Task)
        .filter(models.Task.status == "failed")
        .order_by(models.Task.completed_at.desc(), models.Task.id.desc())
        .limit(limit)
        .all()
    )


def reset_workflows_and_tasks(db: Session) -> None:
    """Delete all workflows and tasks from the database.
    
    Cascading delete: Tasks are deleted when their parent workflow is deleted.
    Intended for testing and demo reset operations.
    
    Args:
        db: SQLAlchemy database session
    
    Returns:
        None (modifies database)
    
    Warning:
        DESTRUCTIVE OPERATION. Permanently deletes all workflows and tasks.
        Should only be called in testing or explicit reset scenarios.
        Protected by permission checks in API layer.
    
    Side Effects:
        - All Task records deleted (cascaded from workflows)
        - All Workflow records deleted
        - Audit logs NOT deleted (immutable)
    
    Example:
        >>> # Reset demo environment
        >>> reset_workflows_and_tasks(db)
        >>> # Re-seed demo data
        >>> seed_demo_data(db)
    """
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
    details: dict[str, Any] | None = None,
) -> models.AuditLog:
    """Create an immutable audit log entry.
    
    Records significant system events for compliance, security, and troubleshooting.
    Audit logs are immutable (never updated) and indexed by event type and timestamp.
    
    Args:
        db: SQLAlchemy database session
        actor: User ID or system identifier initiating the action
        event: Event type (e.g., 'workflow_created', 'task_retried', 'login_failed')
        resource_type: Type of affected resource (e.g., 'workflow', 'task', 'user')
        resource_id: ID of affected resource (nullable for system-level events)
        details: Event-specific metadata dictionary (max 10KB)
            Examples:
            - {'priority': 'high', 'model': 'gpt-4'}
            - {'source_task_id': 42, 'retry_reason': 'timeout'}
            - {'email': 'user@...', 'failure_reason': 'invalid_password'}
    
    Returns:
        Created AuditLog model with auto-generated ID and timestamp
    
    Example:
        >>> create_audit_log(
        ...     db,
        ...     actor="user-123",
        ...     event="workflow_created",
        ...     resource_type="workflow",
        ...     resource_id=42,
        ...     details={"priority": "high", "model": "gpt-4"}
        ... )
    
    Compliance:
        - Immutable records (INSERT only, never UPDATE)
        - Automatically timestamped with utc_now()
        - Indexed for compliance queries
        - Suitable for regulatory audit trails (SOC2, HIPAA, GDPR)
    """
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


def list_audit_logs(db: Session, limit: int = 50) -> list[models.AuditLog]:
    """List most recent audit log entries.
    
    Returns the most recent entries first. Useful for compliance reporting and
    investigating security events.
    
    Args:
        db: SQLAlchemy database session
        limit: Maximum entries to return (default 50, suitable for admin UI)
    
    Returns:
        List of AuditLog models (up to limit)
    
    Sorting:
        Primary: created_at DESC (most recent first)
        Secondary: id DESC (stable ordering)
    
    Use Cases:
        - Security review: Recent user actions
        - Incident investigation: Trace of events before/after incident
        - Compliance reporting: Audit trail exports
        - Admin dashboard: System activity feed
    
    Example:
        >>> logs = list_audit_logs(db, limit=100)
        >>> for log in logs:
        ...     print(f"{log.created_at}: {log.event} by {log.actor}")
    """
    return db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc(), models.AuditLog.id.desc()).limit(limit).all()
