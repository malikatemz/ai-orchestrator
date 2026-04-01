import { API_BASE } from '../lib/env'
import { getAuthToken } from '../lib/auth'
import { captureClientError } from '../lib/monitoring'
import type { ApiErrorResponse, OverviewResponse, TaskFormValues, TaskResponse, WorkflowDetail, WorkflowFormValues, WorkflowSummary } from '../types/orchestrator'

const RETRYABLE_METHODS = new Set(['GET'])
const RETRY_DELAYS_MS = [500, 1500, 3500]

export class ApiClientError extends Error {
  code: string
  severity: string
  retryable: boolean
  requestId?: string
  details: Record<string, unknown>

  constructor(payload: Partial<ApiErrorResponse> & { message?: string }) {
    super(payload.error?.message || payload.message || 'Request failed')
    this.name = 'ApiClientError'
    this.code = payload.error?.code || 'AIORCH-SYS-UNKNOWN'
    this.severity = payload.error?.severity || 'medium'
    this.retryable = payload.error?.retryable || false
    this.requestId = payload.request_id
    this.details = payload.error?.details || {}
  }
}

function wait(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, delayMs)
  })
}

async function parseErrorResponse(response: Response): Promise<ApiClientError> {
  let payload: ApiErrorResponse | null = null
  try {
    payload = (await response.json()) as ApiErrorResponse
  } catch {
    payload = null
  }

  return new ApiClientError(
    payload || {
      message: `Request failed for ${response.url}`,
      request_id: response.headers.get('x-request-id') || undefined,
    }
  )
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method || 'GET'
  const shouldRetry = RETRYABLE_METHODS.has(method.toUpperCase())

  const authToken = getAuthToken()
  const headers = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) || {}),
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  }

  for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers,
      })

      if (!response.ok) {
        const apiError = await parseErrorResponse(response)
        if (shouldRetry && apiError.retryable && attempt < RETRY_DELAYS_MS.length) {
          await wait(RETRY_DELAYS_MS[attempt])
          continue
        }

        captureClientError(apiError, {
          area: 'api',
          code: apiError.code,
          severity: apiError.severity,
          requestId: apiError.requestId,
          retryable: apiError.retryable,
          details: apiError.details,
        })
        throw apiError
      }

      return response.json() as Promise<T>
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }

      if (shouldRetry && attempt < RETRY_DELAYS_MS.length) {
        await wait(RETRY_DELAYS_MS[attempt])
        continue
      }

      const clientError = new ApiClientError({
        message: error instanceof Error ? error.message : `Request failed for ${path}`,
      })
      captureClientError(clientError, {
        area: 'api',
        code: clientError.code,
        severity: clientError.severity,
        requestId: clientError.requestId,
        retryable: clientError.retryable,
      })
      throw clientError
    }
  }

  throw new ApiClientError({ message: `Request failed for ${path}` })
}

export const orchestratorApi = {
  getOverview(): Promise<OverviewResponse> {
    return request<OverviewResponse>('/overview')
  },
  getWorkflow(workflowId: number): Promise<WorkflowDetail> {
    return request<WorkflowDetail>(`/workflows/${workflowId}`)
  },
  createWorkflow(payload: WorkflowFormValues): Promise<WorkflowSummary> {
    return request<WorkflowSummary>('/workflows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  },
  createTask(workflowId: number, payload: TaskFormValues): Promise<TaskResponse> {
    return request<TaskResponse>(`/workflows/${workflowId}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  }
}
