import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { PlatformOpsPage } from './PlatformOpsPage'

vi.mock('next/link', () => ({
  default: ({ children, href, className }: { children: ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock('../common/SeoHead', () => ({
  SeoHead: () => null,
}))

vi.mock('../../services/orchestratorApi', () => ({
  orchestratorApi: {
    getOpsMetrics: vi.fn(async () => ({
      workflows_total: 3,
      tasks_total: 9,
      pending_tasks: 2,
      running_tasks: 1,
      completed_tasks: 5,
      failed_tasks: 1,
      failure_rate: 16.7,
      average_duration_seconds: 2.4,
      recent_failures: [
        {
          id: 1,
          workflow_id: 3,
          source_task_id: null,
          name: 'Recover release checklist',
          agent: 'critic',
          stage: 'failed',
          status: 'failed',
          queue_name: 'high_priority',
          input: 'Recover release checklist',
          output: null,
          error_message: 'timeout',
          retries: 1,
          duration_seconds: null,
          created_at: '2024-01-01T00:00:00Z',
          started_at: null,
          completed_at: '2024-01-01T00:00:00Z',
        },
      ],
      top_failing_workflows: [{ workflow_id: 3, workflow_name: 'Release Review', failed_tasks: 2 }],
      execution_lanes: [{ queue_name: 'high_priority', tasks: 4 }],
    })),
    getAuditLogs: vi.fn(async () => [
      {
        id: 1,
        actor: 'system',
        event: 'task_failed',
        resource_type: 'task',
        resource_id: 10,
        details: {},
        created_at: '2024-01-01T00:00:00Z',
      },
    ]),
  },
}))

describe('PlatformOpsPage', () => {
  it('renders aggregated platform ops metrics and audit logs', async () => {
    render(<PlatformOpsPage />)

    await waitFor(() => {
      expect(screen.getByText('Operational visibility for queues, failures, and audit events.')).toBeTruthy()
    })

    expect(screen.getByText('3')).toBeTruthy()
    expect(screen.getByText('Release Review')).toBeTruthy()
    expect(screen.getByText('task_failed')).toBeTruthy()
  })
})
