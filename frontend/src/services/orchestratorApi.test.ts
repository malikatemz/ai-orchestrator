import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError, orchestratorApi } from './orchestratorApi'

vi.mock('../lib/monitoring', () => ({
  captureClientError: vi.fn(),
}))

describe('orchestratorApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('retries retryable GET failures and succeeds', async () => {
    const fetchMock = vi
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          error: {
            code: 'AIORCH-DEP-001',
            message: 'Database unavailable.',
            severity: 'medium',
            retryable: true,
            details: {},
          },
          request_id: 'req-1',
        }),
        headers: new Headers({ 'x-request-id': 'req-1' }),
        url: 'http://localhost:8000/overview',
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          metrics: { workflows: 1, tasks: 1, running: 0, completed: 1, failed: 0, success_rate: 100 },
          workflows: [],
          recent_tasks: [],
        }),
      } as Response)

    const request = orchestratorApi.getOverview()
    await vi.runAllTimersAsync()
    const payload = await request

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(payload.metrics.workflows).toBe(1)
  })

  it('throws a typed error for non-retryable API failures', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({
        error: {
          code: 'AIORCH-NOTFOUND-001',
          message: 'Workflow not found.',
          severity: 'low',
          retryable: false,
          details: { workflow_id: 3 },
        },
        request_id: 'req-404',
      }),
      headers: new Headers({ 'x-request-id': 'req-404' }),
      url: 'http://localhost:8000/workflows/3',
    } as Response)

    const error = await orchestratorApi.getWorkflow(3).catch((caughtError) => caughtError)

    expect(error).toBeInstanceOf(ApiClientError)
    expect(error).toMatchObject({
      code: 'AIORCH-NOTFOUND-001',
      requestId: 'req-404',
      retryable: false,
    })
  })

  it('does not retry non-idempotent post requests when they fail', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({
        error: {
          code: 'AIORCH-VAL-001',
          message: 'Request validation failed.',
          severity: 'low',
          retryable: false,
          details: {},
        },
        request_id: 'req-post',
      }),
      headers: new Headers({ 'x-request-id': 'req-post' }),
      url: 'http://localhost:8000/workflows',
    } as Response)

    const error = await orchestratorApi
      .createWorkflow({
        name: 'ab',
        description: 'short',
        owner: 'ops',
        priority: 'medium',
        target_model: 'gpt-4.1',
      } as never)
      .catch((caughtError) => caughtError)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(error).toBeInstanceOf(ApiClientError)
    expect(error.code).toBe('AIORCH-VAL-001')
  })

  it('wraps terminal network failures into typed client errors after retries', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockRejectedValue(new Error('network unavailable'))

    const request = orchestratorApi.getOverview().catch((caughtError) => caughtError)
    await vi.runAllTimersAsync()
    const error = await request

    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(error).toBeInstanceOf(ApiClientError)
    expect(error.message).toContain('network unavailable')
  })
})
