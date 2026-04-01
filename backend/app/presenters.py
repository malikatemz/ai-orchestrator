from __future__ import annotations

from . import models, schemas


def model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def model_to_output(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def serialize_overview(data) -> schemas.OverviewResponse:
    return schemas.OverviewResponse(
        metrics=schemas.OverviewMetrics(**data["metrics"]),
        workflows=[serialize_workflow(workflow) for workflow in data["workflows"]],
        recent_tasks=[serialize_task(task) for task in data["recent_tasks"]],
    )


def serialize_task(task: models.Task) -> schemas.TaskResponse:
    return schemas.TaskResponse(
        id=task.id,
        workflow_id=task.workflow_id,
        source_task_id=task.source_task_id,
        name=task.name,
        agent=task.agent,
        stage=task.stage,
        status=task.status,
        queue_name=task.queue_name,
        input=task.input_data,
        output=task.output_data,
        error_message=task.error_message,
        retries=task.retries,
        duration_seconds=task.duration_seconds,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


def serialize_workflow(workflow: models.Workflow) -> schemas.WorkflowSummary:
    tasks = workflow.tasks
    return schemas.WorkflowSummary(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        owner=workflow.owner,
        status=workflow.status,
        priority=workflow.priority,
        target_model=workflow.target_model,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        last_run_at=workflow.last_run_at,
        task_count=len(tasks),
        completed_tasks=sum(task.status == "completed" for task in tasks),
        failed_tasks=sum(task.status == "failed" for task in tasks),
        active_tasks=sum(task.status in {"pending", "running"} for task in tasks),
    )


def serialize_audit_log(entry: models.AuditLog) -> schemas.AuditLogResponse:
    return schemas.AuditLogResponse(
        id=entry.id,
        actor=entry.actor,
        event=entry.event,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        details=entry.details,
        created_at=entry.created_at,
    )


def serialize_ops_metrics(data) -> schemas.OpsMetricsResponse:
    return schemas.OpsMetricsResponse(
        workflows_total=data["workflows_total"],
        tasks_total=data["tasks_total"],
        pending_tasks=data["pending_tasks"],
        running_tasks=data["running_tasks"],
        completed_tasks=data["completed_tasks"],
        failed_tasks=data["failed_tasks"],
        failure_rate=data["failure_rate"],
        average_duration_seconds=data["average_duration_seconds"],
        recent_failures=[serialize_task(task) for task in data["recent_failures"]],
        top_failing_workflows=[
            schemas.FailingWorkflowMetric(**item) for item in data["top_failing_workflows"]
        ],
        execution_lanes=[schemas.ExecutionLaneMetric(**item) for item in data["execution_lanes"]],
    )
