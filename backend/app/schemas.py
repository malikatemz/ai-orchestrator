from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=500)
    owner: str = Field(default="operations", min_length=2, max_length=80)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    target_model: str = Field(default="gpt-4.1-mini", min_length=3, max_length=80)


class TaskCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    input: str = Field(min_length=5, max_length=3000)
    agent: str = Field(default="planner", pattern="^(planner|researcher|critic|executor)$")


class TaskResponse(BaseModel):
    id: int
    workflow_id: int
    source_task_id: Optional[int]
    name: str
    agent: str
    stage: str
    status: str
    queue_name: str
    input: str
    output: Optional[str]
    error_message: Optional[str]
    retries: int
    duration_seconds: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class WorkflowSummary(BaseModel):
    id: int
    name: str
    description: str
    owner: str
    status: str
    priority: str
    target_model: str
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime]
    task_count: int
    completed_tasks: int
    failed_tasks: int
    active_tasks: int


class WorkflowDetail(WorkflowSummary):
    tasks: List[TaskResponse]


class OverviewMetrics(BaseModel):
    workflows: int
    tasks: int
    running: int
    completed: int
    failed: int
    success_rate: float


class OverviewResponse(BaseModel):
    metrics: OverviewMetrics
    workflows: List[WorkflowSummary]
    recent_tasks: List[TaskResponse]


class HealthResponse(BaseModel):
    status: str
    database: str
    queue_mode: str
    timestamp: datetime


class AppConfigResponse(BaseModel):
    app_mode: str
    demo_mode: bool
    auth_required: bool
    demo_seed_enabled: bool
    public_app_url: str
    public_api_url: str


class AuditLogResponse(BaseModel):
    id: int
    actor: str
    event: str
    resource_type: str
    resource_id: Optional[int]
    details: dict[str, Any]
    created_at: datetime


class ExecutionLaneMetric(BaseModel):
    queue_name: str
    tasks: int


class FailingWorkflowMetric(BaseModel):
    workflow_id: int
    workflow_name: str
    failed_tasks: int


class OpsMetricsResponse(BaseModel):
    workflows_total: int
    tasks_total: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    failure_rate: float
    average_duration_seconds: float
    recent_failures: List[TaskResponse]
    top_failing_workflows: List[FailingWorkflowMetric]
    execution_lanes: List[ExecutionLaneMetric]


class ErrorEnvelopeItem(BaseModel):
    code: str
    message: str
    severity: str
    retryable: bool
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorEnvelopeItem
    request_id: str


class CheckoutSessionRequest(BaseModel):
    """Request to create a checkout session for billing."""
    price_id: str
    success_url: str
    cancel_url: str
    customer_email: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CheckoutSessionResponse(BaseModel):
    """Response containing checkout session URL."""
    checkout_url: str
    session_id: str


class UsageResponse(BaseModel):
    """Response containing usage metrics."""
    period_start: datetime
    period_end: datetime
    usage_amount: float
    unit: str
