export type WorkflowPriority = 'low' | 'medium' | 'high' | 'critical'
export type AgentRole = 'planner' | 'researcher' | 'critic' | 'executor'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'
export type ErrorSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface AppConfigResponse {
  app_mode: string
  demo_mode: boolean
  auth_required: boolean
  demo_seed_enabled: boolean
  public_app_url: string
  public_api_url: string
}

export interface OverviewMetrics {
  workflows: number
  tasks: number
  running: number
  completed: number
  failed: number
  success_rate: number
}

export interface TaskResponse {
  id: number
  workflow_id: number
  source_task_id?: number | null
  name: string
  agent: AgentRole
  stage: string
  status: TaskStatus
  queue_name: string
  input: string
  output?: string | null
  error_message?: string | null
  retries: number
  duration_seconds?: number | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
}

export interface WorkflowSummary {
  id: number
  name: string
  description: string
  owner: string
  status: string
  priority: WorkflowPriority
  target_model: string
  created_at: string
  updated_at: string
  last_run_at?: string | null
  task_count: number
  completed_tasks: number
  failed_tasks: number
  active_tasks: number
}

export interface WorkflowDetail extends WorkflowSummary {
  tasks: TaskResponse[]
}

export interface OverviewResponse {
  metrics: OverviewMetrics
  workflows: WorkflowSummary[]
  recent_tasks: TaskResponse[]
}

export interface WorkflowFormValues {
  name: string
  description: string
  owner: string
  priority: WorkflowPriority
  target_model: string
}

export interface TaskFormValues {
  name: string
  input: string
  agent: AgentRole
}

export interface AuditLogResponse {
  id: number
  actor: string
  event: string
  resource_type: string
  resource_id?: number | null
  details: Record<string, unknown>
  created_at: string
}

export interface ExecutionLaneMetric {
  queue_name: string
  tasks: number
}

export interface FailingWorkflowMetric {
  workflow_id: number
  workflow_name: string
  failed_tasks: number
}

export interface OpsMetricsResponse {
  workflows_total: number
  tasks_total: number
  pending_tasks: number
  running_tasks: number
  completed_tasks: number
  failed_tasks: number
  failure_rate: number
  average_duration_seconds: number
  recent_failures: TaskResponse[]
  top_failing_workflows: FailingWorkflowMetric[]
  execution_lanes: ExecutionLaneMetric[]
}

export interface ApiErrorPayload {
  code: string
  message: string
  severity: ErrorSeverity
  retryable: boolean
  details: Record<string, unknown>
}

export interface ApiErrorResponse {
  error: ApiErrorPayload
  request_id: string
}
