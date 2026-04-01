from typing import List

from . import models, schemas


def model_to_dict(model):
    """Convert a Pydantic model to dict, handling v1/v2 compatibility."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def model_to_output(model):
    """Convert a model to output dict, handling v1/v2 compatibility."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def serialize_overview(data) -> schemas.OverviewResponse:
    """Serialize overview data to response schema."""
    return schemas.OverviewResponse(
        metrics=schemas.OverviewMetrics(**data["metrics"]),
        workflows=[serialize_workflow(workflow) for workflow in data["workflows"]],
        recent_tasks=[serialize_task(task) for task in data["recent_tasks"]],
    )


def serialize_task(task: models.Task) -> schemas.TaskResponse:
    """Serialize a Task model to TaskResponse schema."""
    return schemas.TaskResponse(
        id=task.id,
        workflow_id=task.workflow_id,
        name=task.name,
        agent=task.agent,
        stage=task.stage,
        status=task.status,
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
    """Serialize a Workflow model to WorkflowSummary schema."""
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