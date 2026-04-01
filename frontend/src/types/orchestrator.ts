export type WorkflowPriority = 'low' | 'medium' | 'high' | 'critical'
export type AgentRole = 'planner' | 'researcher' | 'critic' | 'executor'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'
export type ErrorSeverity = 'low' | 'medium' | 'high' | 'critical'

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
  name: string
  agent: AgentRole
  stage: string
  status: TaskStatus
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
