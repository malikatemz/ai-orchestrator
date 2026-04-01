import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { DashboardPage } from './DashboardPage'

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}))

vi.mock('../../hooks/useDashboard', () => ({
  useDashboard: vi.fn(() => ({
    overview: {
      metrics: { workflows: 2, tasks: 5, running: 1, completed: 4, failed: 1, success_rate: 80 },
      workflows: [
        {
          id: 1,
          name: 'Ops Flow',
          description: 'Handle production operations.',
          owner: 'ops',
          status: 'active',
          priority: 'high',
          target_model: 'gpt-4.1',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          last_run_at: null,
          task_count: 3,
          completed_tasks: 2,
          failed_tasks: 1,
          active_tasks: 0,
        },
      ],
      recent_tasks: [],
    },
    selectedWorkflow: {
      id: 1,
      name: 'Ops Flow',
      description: 'Handle production operations.',
      owner: 'ops',
      status: 'active',
      priority: 'high',
      target_model: 'gpt-4.1',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      last_run_at: null,
      task_count: 3,
      completed_tasks: 2,
      failed_tasks: 1,
      active_tasks: 0,
      tasks: [],
    },
    selectedWorkflowId: 1,
    workflowForm: { name: '', description: '', owner: 'ops', priority: 'medium', target_model: 'gpt-4.1-mini' },
    taskForm: { name: '', input: '', agent: 'planner' },
    loading: false,
    submitting: false,
    error: '',
    selectWorkflow: vi.fn(),
    setWorkflowForm: vi.fn(),
    setTaskForm: vi.fn(),
    createWorkflow: vi.fn(),
    createTask: vi.fn(),
  })),
}))

vi.mock('../common/SeoHead', () => ({
  SeoHead: () => null,
}))

describe('DashboardPage', () => {
  it('renders dashboard metrics and key workflow sections on the happy path', () => {
    render(<DashboardPage />)

    expect(screen.getByText('Ship orchestrated AI work with visibility, retries, and live execution context.')).toBeTruthy()
    expect(screen.getByText('Workflows')).toBeTruthy()
    expect(screen.getByText('Ops Flow')).toBeTruthy()
    expect(screen.getByText('Success Rate')).toBeTruthy()
  })

  it('renders loading state when dashboard data is still resolving', async () => {
    const { useDashboard } = await import('../../hooks/useDashboard')
    vi.mocked(useDashboard).mockReturnValueOnce({
      overview: null,
      selectedWorkflow: null,
      selectedWorkflowId: null,
      workflowForm: { name: '', description: '', owner: 'ops', priority: 'medium', target_model: 'gpt-4.1-mini' },
      taskForm: { name: '', input: '', agent: 'planner' },
      loading: true,
      submitting: false,
      error: '',
      selectWorkflow: vi.fn(),
      setWorkflowForm: vi.fn(),
      setTaskForm: vi.fn(),
      createWorkflow: vi.fn(),
      createTask: vi.fn(),
    })

    render(<DashboardPage />)

    expect(screen.getByText('Loading orchestrator state...')).toBeTruthy()
  })

  it('renders the top-level error banner when the hook exposes an error', async () => {
    const { useDashboard } = await import('../../hooks/useDashboard')
    vi.mocked(useDashboard).mockReturnValueOnce({
      overview: null,
      selectedWorkflow: null,
      selectedWorkflowId: null,
      workflowForm: { name: '', description: '', owner: 'ops', priority: 'medium', target_model: 'gpt-4.1-mini' },
      taskForm: { name: '', input: '', agent: 'planner' },
      loading: false,
      submitting: false,
      error: 'Live data is temporarily unavailable.',
      selectWorkflow: vi.fn(),
      setWorkflowForm: vi.fn(),
      setTaskForm: vi.fn(),
      createWorkflow: vi.fn(),
      createTask: vi.fn(),
    })

    render(<DashboardPage />)

    expect(screen.getByText('Live data is temporarily unavailable.')).toBeTruthy()
  })
})
