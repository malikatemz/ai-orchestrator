from datetime import datetime
from typing import List, Optional

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
    name: str
    agent: str
    stage: str
    status: str
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
