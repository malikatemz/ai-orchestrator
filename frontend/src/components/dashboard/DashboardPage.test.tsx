import React from 'react'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { DashboardPage } from './DashboardPage'

vi.mock('next/link', () => ({
  default: ({ children, href, className }: { children: ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock('../../hooks/useDashboard', () => ({
  useDashboard: vi.fn(() => ({
    appConfig: {
      app_mode: 'demo',
      demo_mode: true,
      auth_required: false,
      demo_seed_enabled: true,
      public_app_url: 'https://example.com',
      public_api_url: 'https://api.example.com',
    },
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
    retryTask: vi.fn(),
    resetDemo: vi.fn(),
  })),
}))

vi.mock('../common/SeoHead', () => ({
  SeoHead: () => null,
}))

describe('DashboardPage', () => {
  it('renders dashboard metrics, demo callout, and workflow sections on the happy path', () => {
    render(<DashboardPage />)

    expect(screen.getByText('Ship orchestrated AI work with visibility, retries, and live execution context.')).toBeTruthy()
    expect(screen.getByText('Reset demo data')).toBeTruthy()
    expect(screen.getAllByText('Workflows')[0]).toBeTruthy()
    expect(screen.getAllByText('Ops Flow')[0]).toBeTruthy()
    expect(screen.getAllByText('Platform Ops')[0]).toBeTruthy()
  })

  it('renders loading state when dashboard data is still resolving', async () => {
    const { useDashboard } = await import('../../hooks/useDashboard')
    vi.mocked(useDashboard).mockReturnValueOnce({
      appConfig: null,
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
      retryTask: vi.fn(),
      resetDemo: vi.fn(),
    })

    render(<DashboardPage />)

    expect(screen.getByText('Loading orchestrator state...')).toBeTruthy()
  })
})
