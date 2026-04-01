import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDashboard } from './useDashboard'

const appConfigPayload = {
  app_mode: 'demo',
  demo_mode: true,
  auth_required: false,
  demo_seed_enabled: true,
  public_app_url: 'https://example.com',
  public_api_url: 'https://api.example.com',
}

const overviewPayload = {
  metrics: { workflows: 1, tasks: 1, running: 0, completed: 1, failed: 0, success_rate: 100 },
  workflows: [
    {
      id: 1,
      name: 'Ops Workflow',
      description: 'Monitor operations activity for production incidents.',
      owner: 'ops',
      status: 'active',
      priority: 'high',
      target_model: 'gpt-4.1',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      last_run_at: null,
      task_count: 1,
      completed_tasks: 1,
      failed_tasks: 0,
      active_tasks: 0,
    },
  ],
  recent_tasks: [],
}

const workflowPayload = {
  ...overviewPayload.workflows[0],
  tasks: [
    {
      id: 10,
      workflow_id: 1,
      source_task_id: null,
      name: 'Recover incident brief',
      agent: 'critic',
      stage: 'failed',
      status: 'failed',
      queue_name: 'high_priority',
      input: 'Summarize the incident timeline.',
      output: null,
      error_message: 'model timed out',
      retries: 1,
      duration_seconds: null,
      created_at: '2024-01-01T00:00:00Z',
      started_at: null,
      completed_at: '2024-01-01T00:00:00Z',
    },
  ],
}

vi.mock('../services/orchestratorApi', () => ({
  orchestratorApi: {
    getAppConfig: vi.fn(),
    getOverview: vi.fn(),
    getWorkflow: vi.fn(),
    createWorkflow: vi.fn(),
    createTask: vi.fn(),
    retryTask: vi.fn(),
    seedDemo: vi.fn(),
  },
  ApiClientError: class ApiClientError extends Error {
    requestId?: string
  },
}))

vi.mock('../lib/monitoring', () => ({
  captureClientError: vi.fn(),
}))

vi.mock('../lib/auth', () => ({
  getAuthToken: vi.fn(() => null),
}))

describe('useDashboard', () => {
  beforeEach(async () => {
    vi.restoreAllMocks()
    const { orchestratorApi } = await import('../services/orchestratorApi')
    vi.mocked(orchestratorApi.getAppConfig).mockResolvedValue(appConfigPayload)
    vi.mocked(orchestratorApi.getOverview).mockResolvedValue(overviewPayload)
    vi.mocked(orchestratorApi.getWorkflow).mockResolvedValue(workflowPayload)
    vi.mocked(orchestratorApi.seedDemo).mockResolvedValue(overviewPayload)
    vi.mocked(orchestratorApi.retryTask).mockResolvedValue({
      ...workflowPayload.tasks[0],
      id: 11,
      workflow_id: 1,
      status: 'pending',
      stage: 'queued',
    })
  })

  it('loads app config, overview, and selected workflow on boot', async () => {
    const { result } = renderHook(() => useDashboard())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.appConfig?.demo_mode).toBe(true)
    expect(result.current.overview?.metrics.workflows).toBe(1)
    expect(result.current.selectedWorkflow?.id).toBe(1)
  })

  it('resets demo data when demo reset is triggered', async () => {
    const { result } = renderHook(() => useDashboard())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.resetDemo()
    })

    expect(result.current.overview?.workflows[0].id).toBe(1)
  })

  it('retries a failed task and refreshes the selected workflow', async () => {
    const { orchestratorApi } = await import('../services/orchestratorApi')
    const { result } = renderHook(() => useDashboard())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // Clear the call history after boot completes so we can track what retryTask does
    vi.mocked(orchestratorApi.getOverview).mockClear()

    await act(async () => {
      await result.current.retryTask(10)
    })

    expect(vi.mocked(orchestratorApi.retryTask)).toHaveBeenCalledWith(10)
    expect(vi.mocked(orchestratorApi.getOverview)).toHaveBeenCalledTimes(1)
  })
})
