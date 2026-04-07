from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    """Request to create a new workflow.
    
    Workflows are reusable templates for multi-step AI-assisted processes.
    This request creates a workflow definition that can be executed multiple times
    with different inputs via the /tasks endpoint.
    
    Attributes:
        name: Workflow display name (3-120 chars)
            Examples: "Email Summarizer", "Code Reviewer", "Data Analyzer"
        description: Detailed description of workflow purpose (10-500 chars)
            Explains what the workflow does and expected outputs
        owner: User ID of workflow creator (default: "operations")
            Can be overridden by demo/admin users
        priority: Default execution priority (low/medium/high/critical)
            Used for task queueing when not specified per-task
        target_model: Default LLM model (gpt-4.1-mini, claude-3-opus, etc.)
            Used for task execution when not specified per-task
    
    Validation:
        - name: 3-120 characters, required
        - description: 10-500 characters, required
        - owner: 2-80 characters, defaults to "operations"
        - priority: Regex enforced (low|medium|high|critical)
        - target_model: 3-80 characters, defaults to "gpt-4.1-mini"
    
    Example:
        >>> request = WorkflowCreate(
        ...     name="Email Summarizer",
        ...     description="Summarize incoming emails into concise bullet points",
        ...     owner="user-123",
        ...     priority="high",
        ...     target_model="gpt-4"
        ... )
    """
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=500)
    owner: str = Field(default="operations", min_length=2, max_length=80)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    target_model: str = Field(default="gpt-4.1-mini", min_length=3, max_length=80)


class TaskCreate(BaseModel):
    """Request to create and execute a task for a workflow.
    
    Creates a new task instance within a workflow and queues it for execution.
    The task will execute against the workflow's definition using the specified inputs.
    
    Attributes:
        name: Task display name (3-120 chars)
            Examples: "Process this email", "Review code snippet", "Analyze data"
        input: Task input data (5-3000 chars)
            JSON-serialized or text input for the workflow
            Examples: '{"email": "long email text..."}', '{"code": "def foo()..."}' 
        agent: AI agent type to execute (planner/researcher/critic/executor)
            Determines which agent handles the task
            Default: "planner" (orchestration/routing)
    
    Validation:
        - name: 3-120 characters, required
        - input: 5-3000 characters, required (prevents accidental empty inputs)
        - agent: Regex enforced (planner|researcher|critic|executor)
    
    Example:
        >>> request = TaskCreate(
        ...     name="Summarize this email",
        ...     input='{"email": "Dear Team, This is a long email..."}',
        ...     agent="executor"
        ... )
    """
    name: str = Field(min_length=3, max_length=120)
    input: str = Field(min_length=5, max_length=3000)
    agent: str = Field(default="planner", pattern="^(planner|researcher|critic|executor)$")


class TaskResponse(BaseModel):
    """Response containing full task execution details.
    
    Returned from task creation, retrieval, and listing endpoints.
    Represents a single execution instance of a workflow.
    
    Attributes:
        id: Task unique identifier (auto-assigned)
        workflow_id: Parent workflow ID
        source_task_id: Original task ID if this is a retry (null for first attempt)
        name: Task display name
        agent: Agent type (planner/researcher/critic/executor)
        stage: Execution stage (queued/started/processing/completed)
        status: Task outcome (pending/running/succeeded/failed/retrying)
        queue_name: Celery queue assignment (default/high_priority/low_cost)
        input: Task input data
        output: Task result (null until completion)
        error_message: Error description if failed (null on success)
        retries: Number of retry attempts
        duration_seconds: Wall-clock execution time (null if not completed)
        created_at: Submission timestamp
        started_at: Execution start timestamp (null if not started)
        completed_at: Execution end timestamp (null if still running)
    
    Example:
        >>> response = {
        ...     "id": 123,
        ...     "workflow_id": 42,
        ...     "source_task_id": None,
        ...     "name": "Summarize email",
        ...     "status": "queued",
        ...     "output": None,
        ...     "created_at": "2026-04-07T07:11:12Z"
        ... }
    """
    id: int
    workflow_id: int
    source_task_id: int | None
    name: str
    agent: str
    stage: str
    status: str
    queue_name: str
    input: str
    output: str | None
    error_message: str | None
    retries: int
    duration_seconds: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class WorkflowSummary(BaseModel):
    """Summary of a workflow with execution metrics.
    
    Returned from workflow list/get endpoints. Contains workflow definition
    plus summary statistics (task counts, success rates).
    
    Attributes:
        id: Workflow unique identifier
        name: Workflow display name
        description: Workflow purpose
        owner: Creator's user ID
        status: Current status (active/paused/archived/draft)
        priority: Default task priority
        target_model: Default LLM model
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        last_run_at: Most recent task completion timestamp (null if never executed)
        task_count: Total tasks ever executed for this workflow
        completed_tasks: Number of successfully completed tasks
        failed_tasks: Number of failed tasks
        active_tasks: Number of currently running tasks
    
    Example:
        >>> response = {
        ...     "id": 42,
        ...     "name": "Email Summarizer",
        ...     "status": "active",
        ...     "task_count": 156,
        ...     "completed_tasks": 153,
        ...     "failed_tasks": 3,
        ...     "active_tasks": 0,
        ...     "success_rate": 0.981
        ... }
    """
    id: int
    name: str
    description: str
    owner: str
    status: str
    priority: str
    target_model: str
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    task_count: int
    completed_tasks: int
    failed_tasks: int
    active_tasks: int


class WorkflowDetail(WorkflowSummary):
    """Extended workflow response with full task history.
    
    Returned from GET /workflows/{id} endpoint. Includes all tasks
    ever executed for the workflow (use task filters for large histories).
    
    Inherits from WorkflowSummary, adds:
    
    Attributes:
        tasks: List of all TaskResponse objects for this workflow
            Ordered by creation time (newest first)
            May be large for workflows with long histories
    
    Example:
        >>> response = {
        ...     **workflow_summary_fields,
        ...     "tasks": [
        ...         {"id": 123, "status": "succeeded", ...},
        ...         {"id": 122, "status": "failed", ...},
        ...     ]
        ... }
    """
    tasks: list[TaskResponse]


class OverviewMetrics(BaseModel):
    """Summary metrics for dashboard overview.
    
    High-level statistics across all workflows and tasks.
    Used for dashboard quick-view cards.
    
    Attributes:
        workflows: Total number of workflows
        tasks: Total number of tasks (across all workflows)
        running: Currently executing tasks
        completed: Successfully completed tasks
        failed: Failed tasks
        success_rate: Percentage of completed tasks that succeeded (0.0-1.0)
    
    Example:
        >>> metrics = {
        ...     "workflows": 12,
        ...     "tasks": 456,
        ...     "running": 3,
        ...     "completed": 440,
        ...     "failed": 13,
        ...     "success_rate": 0.971
        ... }
    """
    workflows: int
    tasks: int
    running: int
    completed: int
    failed: int
    success_rate: float


class OverviewResponse(BaseModel):
    """User dashboard overview combining metrics and recent data.
    
    Returned from GET /overview endpoint. Provides personalized view
    of user's workflows and recent activity.
    
    Attributes:
        metrics: Summary statistics across user's workflows
        workflows: User's accessible workflows (limited to recent)
        recent_tasks: Most recent tasks across user's workflows
    
    Example:
        >>> response = {
        ...     "metrics": {...},
        ...     "workflows": [...],
        ...     "recent_tasks": [...]
        ... }
    """
    metrics: OverviewMetrics
    workflows: list[WorkflowSummary]
    recent_tasks: list[TaskResponse]


class HealthResponse(BaseModel):
    """System health status check response.
    
    Returned from GET /health endpoint. Indicates whether API and
    dependencies are operational.
    
    Attributes:
        status: Overall status (ok/degraded/down)
        database: Database connectivity (connected/disconnected/degraded)
        queue_mode: Task execution mode (celery/inline/celery-with-fallback)
        timestamp: Server timestamp when health check ran
    
    Example:
        >>> response = {
        ...     "status": "ok",
        ...     "database": "connected",
        ...     "queue_mode": "celery-with-inline-fallback",
        ...     "timestamp": "2026-04-07T07:11:12Z"
        ... }
    """
    status: str
    database: str
    queue_mode: str
    timestamp: datetime


class AppConfigResponse(BaseModel):
    """Application configuration and feature flags.
    
    Returned from GET /app-config endpoint. Allows clients to
    adapt behavior based on deployment configuration.
    
    Attributes:
        app_mode: Deployment mode (development/staging/production)
        demo_mode: Whether public demo mode is enabled
        auth_required: Whether authentication is mandatory
        demo_seed_enabled: Whether demo data can be reseeded
        public_app_url: Base URL for web application
        public_api_url: Base URL for API
    
    Example:
        >>> response = {
        ...     "app_mode": "production",
        ...     "demo_mode": False,
        ...     "auth_required": True,
        ...     "public_app_url": "https://app.example.com",
        ...     "public_api_url": "https://api.example.com"
        ... }
    """
    app_mode: str
    demo_mode: bool
    auth_required: bool
    demo_seed_enabled: bool
    public_app_url: str
    public_api_url: str


class AuditLogResponse(BaseModel):
    """Audit log entry for compliance and troubleshooting.
    
    Immutable record of significant system events. Used for security audits,
    incident investigation, and compliance reporting.
    
    Attributes:
        id: Audit log unique identifier
        actor: User or system initiating the action
        event: Event type (workflow_created, task_retried, etc.)
        resource_type: Type of affected resource (workflow, task, user)
        resource_id: ID of affected resource (null for system events)
        details: Event-specific metadata dictionary
        created_at: When event occurred
    
    Example:
        >>> response = {
        ...     "id": 999,
        ...     "actor": "user-123",
        ...     "event": "workflow_created",
        ...     "resource_type": "workflow",
        ...     "resource_id": 42,
        ...     "details": {"priority": "high", "model": "gpt-4"},
        ...     "created_at": "2026-04-07T07:11:12Z"
        ... }
    """
    id: int
    actor: str
    event: str
    resource_type: str
    resource_id: int | None
    details: dict[str, Any]
    created_at: datetime


class ExecutionLaneMetric(BaseModel):
    """Queue/lane execution statistics.
    
    Shows task distribution across Celery queues (lanes).
    Used for monitoring queue health and load balancing.
    
    Attributes:
        queue_name: Celery queue name (default/high_priority/low_cost)
        tasks: Number of tasks in this queue
    
    Example:
        >>> {"queue_name": "high_priority", "tasks": 12}
    """
    queue_name: str
    tasks: int


class FailingWorkflowMetric(BaseModel):
    """Workflow-level failure statistics.
    
    Identifies workflows with high failure rates for prioritization.
    Used in ops dashboard for troubleshooting.
    
    Attributes:
        workflow_id: Workflow identifier
        workflow_name: Workflow display name
        failed_tasks: Count of failed tasks for this workflow
    
    Example:
        >>> {
        ...     "workflow_id": 42,
        ...     "workflow_name": "Email Summarizer",
        ...     "failed_tasks": 5
        ... }
    """
    workflow_id: int
    workflow_name: str
    failed_tasks: int


class OpsMetricsResponse(BaseModel):
    """Comprehensive operations metrics for admin dashboard.
    
    Returned from GET /ops/metrics (admin-only). Contains system health,
    performance, and failure analysis data.
    
    Attributes:
        workflows_total: Total workflows in system
        tasks_total: Total tasks ever executed
        pending_tasks: Tasks waiting in queue
        running_tasks: Currently executing tasks
        completed_tasks: Successfully completed tasks
        failed_tasks: Failed tasks
        failure_rate: Percentage of tasks that failed (0.0-1.0)
        average_duration_seconds: Mean execution time
        recent_failures: List of most recent failed tasks (for investigation)
        top_failing_workflows: Workflows with highest failure counts (for prioritization)
        execution_lanes: Task distribution across Celery queues (for load analysis)
    
    Example:
        >>> response = {
        ...     "workflows_total": 50,
        ...     "tasks_total": 5000,
        ...     "failure_rate": 0.025,
        ...     "pending_tasks": 15,
        ...     "running_tasks": 8,
        ...     "recent_failures": [...],
        ...     "top_failing_workflows": [
        ...         {"workflow_id": 7, "workflow_name": "Bug Reporter", "failed_tasks": 42}
        ...     ],
        ...     "execution_lanes": [
        ...         {"queue_name": "high_priority", "tasks": 20},
        ...         {"queue_name": "default", "tasks": 150}
        ...     ]
        ... }
    """
    workflows_total: int
    tasks_total: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    failure_rate: float
    average_duration_seconds: float
    recent_failures: list[TaskResponse]
    top_failing_workflows: list[FailingWorkflowMetric]
    execution_lanes: list[ExecutionLaneMetric]


class ErrorEnvelopeItem(BaseModel):
    """Error details within error response envelope.
    
    Structured error information returned from API errors.
    Supports retry logic and granular error handling.
    
    Attributes:
        code: Machine-readable error code (INVALID_REQUEST, UNAUTHORIZED, etc.)
        message: Human-readable error message
        severity: Error severity (LOW/MEDIUM/HIGH/CRITICAL)
        retryable: Whether client should retry this request
        details: Additional error context (varies by error type)
    
    Example:
        >>> error = {
        ...     "code": "INVALID_REQUEST",
        ...     "message": "Workflow not found",
        ...     "severity": "MEDIUM",
        ...     "retryable": False,
        ...     "details": {"workflow_id": 99999}
        ... }
    """
    code: str
    message: str
    severity: str
    retryable: bool
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    """Standard error response envelope.
    
    All API errors return this structure for consistent error handling.
    Includes error details and request ID for troubleshooting.
    
    Attributes:
        error: ErrorEnvelopeItem with detailed error information
        request_id: Request identifier for correlation with server logs
    
    Example:
        >>> response = {
        ...     "error": {
        ...         "code": "UNAUTHORIZED",
        ...         "message": "Invalid authentication token",
        ...         "severity": "HIGH",
        ...         "retryable": False,
        ...         "details": {}
        ...     },
        ...     "request_id": "req-abc123xyz"
        ... }
    """
    error: ErrorEnvelopeItem
    request_id: str


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session for billing.
    
    Used to initiate subscription purchases or upgrades via Stripe.
    Initiates the hosted checkout experience.
    
    Attributes:
        price_id: Stripe Price ID for the product being purchased
        success_url: Redirect URL after successful payment
        cancel_url: Redirect URL if customer cancels checkout
        customer_email: Pre-fill email in checkout (optional)
        metadata: Custom metadata to attach to Stripe session
    
    Example:
        >>> request = {
        ...     "price_id": "price_1ABC...",
        ...     "success_url": "https://app.example.com/billing/success",
        ...     "cancel_url": "https://app.example.com/billing/cancel",
        ...     "customer_email": "user@example.com",
        ...     "metadata": {"plan": "professional"}
        ... }
    """
    price_id: str
    success_url: str
    cancel_url: str
    customer_email: str | None = None
    metadata: dict[str, Any] | None = None


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
