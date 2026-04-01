import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDashboard } from './useDashboard'

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
  tasks: [],
}

vi.mock('../services/orchestratorApi', () => ({
  orchestratorApi: {
    getOverview: vi.fn(),
    getWorkflow: vi.fn(),
    createWorkflow: vi.fn(),
    createTask: vi.fn(),
  },
  ApiClientError: class ApiClientError extends Error {
    requestId?: string
  },
}))

vi.mock('../lib/monitoring', () => ({
  captureClientError: vi.fn(),
}))

describe('useDashboard', () => {
  beforeEach(async () => {
    vi.restoreAllMocks()
    const { orchestratorApi } = await import('../services/orchestratorApi')
    vi.mocked(orchestratorApi.getOverview).mockResolvedValue(overviewPayload)
    vi.mocked(orchestratorApi.getWorkflow).mockResolvedValue(workflowPayload)
  })

  it('loads overview and selected workflow on boot', async () => {
    const { result } = renderHook(() => useDashboard())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.overview?.metrics.workflows).toBe(1)
    expect(result.current.selectedWorkflow?.id).toBe(1)
  })

  it('keeps stale overview when refresh fails after initial success', async () => {
    const { orchestratorApi } = await import('../services/orchestratorApi')
    vi.mocked(orchestratorApi.getOverview)
      .mockResolvedValueOnce(overviewPayload)
      .mockRejectedValueOnce(new Error('network down'))
    vi.mocked(orchestratorApi.getWorkflow).mockResolvedValue(workflowPayload)
    vi.mocked(orchestratorApi.createWorkflow).mockResolvedValue({
      ...overviewPayload.workflows[0],
      id: 2,
    })

    const { result } = renderHook(() => useDashboard())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.createWorkflow()
    })

    expect(result.current.overview?.metrics.workflows).toBe(1)
    expect(result.current.error).toContain('network down')
  })
})
