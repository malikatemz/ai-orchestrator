import { useCallback, useEffect, useMemo, useState } from 'react'

import { captureClientError } from '../lib/monitoring'
import { ApiClientError, orchestratorApi } from '../services/orchestratorApi'
import type { OverviewResponse, TaskFormValues, WorkflowDetail, WorkflowFormValues } from '../types/orchestrator'

const DEFAULT_WORKFLOW_FORM: WorkflowFormValues = {
  name: '',
  description: '',
  owner: 'operations',
  priority: 'medium',
  target_model: 'gpt-4.1-mini'
}

const DEFAULT_TASK_FORM: TaskFormValues = {
  name: '',
  input: '',
  agent: 'planner'
}

function toUserMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiClientError) {
    return `${error.message}${error.requestId ? ` Reference: ${error.requestId}` : ''}`
  }

  return error instanceof Error ? error.message : fallback
}

interface UseDashboardResult {
  overview: OverviewResponse | null
  selectedWorkflow: WorkflowDetail | null
  selectedWorkflowId: number | null
  workflowForm: WorkflowFormValues
  taskForm: TaskFormValues
  loading: boolean
  submitting: boolean
  error: string
  selectWorkflow: (workflowId: number) => Promise<void>
  setWorkflowForm: (values: WorkflowFormValues) => void
  setTaskForm: (values: TaskFormValues) => void
  createWorkflow: () => Promise<void>
  createTask: () => Promise<void>
}

export function useDashboard(): UseDashboardResult {
  const [overview, setOverview] = useState<OverviewResponse | null>(null)
  const [staleOverview, setStaleOverview] = useState<OverviewResponse | null>(null)
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDetail | null>(null)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null)
  const [workflowForm, setWorkflowForm] = useState<WorkflowFormValues>(DEFAULT_WORKFLOW_FORM)
  const [taskForm, setTaskForm] = useState<TaskFormValues>(DEFAULT_TASK_FORM)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const hydrateSelectedWorkflow = useCallback(async (workflowId: number) => {
    const workflow = await orchestratorApi.getWorkflow(workflowId)
    setSelectedWorkflow(workflow)
    setSelectedWorkflowId(workflowId)
  }, [])

  const refreshOverview = useCallback(
    async (preferredId?: number) => {
      const nextOverview = await orchestratorApi.getOverview()
      setOverview(nextOverview)
      setStaleOverview(nextOverview)

      const nextWorkflowId = preferredId || selectedWorkflowId || nextOverview.workflows[0]?.id
      if (nextWorkflowId) {
        await hydrateSelectedWorkflow(nextWorkflowId)
      } else {
        setSelectedWorkflow(null)
        setSelectedWorkflowId(null)
      }
    },
    [hydrateSelectedWorkflow, selectedWorkflowId]
  )

  useEffect(() => {
    let active = true

    async function boot() {
      try {
        await refreshOverview()
      } catch (caughtError) {
        if (active) {
          captureClientError(caughtError, { area: 'frontend', severity: 'medium' })
          setError(toUserMessage(caughtError, 'Unable to load dashboard'))
          if (staleOverview) {
            setOverview(staleOverview)
          }
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void boot()

    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void refreshOverview().catch((caughtError) => {
          captureClientError(caughtError, { area: 'frontend', severity: 'medium' })
          setError(staleOverview ? 'Live data is temporarily unavailable. Showing the last known state.' : toUserMessage(caughtError, 'Unable to refresh dashboard'))
          if (staleOverview) {
            setOverview(staleOverview)
          }
        })
      }
    }, 30000)

    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [refreshOverview, staleOverview])

  const selectWorkflow = useCallback(async (workflowId: number) => {
    setError('')
    await hydrateSelectedWorkflow(workflowId)
  }, [hydrateSelectedWorkflow])

  const createWorkflow = useCallback(async () => {
    setSubmitting(true)
    setError('')

    try {
      const workflow = await orchestratorApi.createWorkflow(workflowForm)
      setWorkflowForm(DEFAULT_WORKFLOW_FORM)
      await refreshOverview(workflow.id)
    } catch (caughtError) {
      captureClientError(caughtError, { area: 'frontend', severity: 'medium' })
      setError(toUserMessage(caughtError, 'Workflow creation failed'))
    } finally {
      setSubmitting(false)
    }
  }, [refreshOverview, workflowForm])

  const createTask = useCallback(async () => {
    if (!selectedWorkflowId) {
      return
    }

    setSubmitting(true)
    setError('')

    try {
      await orchestratorApi.createTask(selectedWorkflowId, taskForm)
      setTaskForm(DEFAULT_TASK_FORM)
      await refreshOverview(selectedWorkflowId)
    } catch (caughtError) {
      captureClientError(caughtError, { area: 'frontend', severity: 'medium' })
      setError(toUserMessage(caughtError, 'Task dispatch failed'))
    } finally {
      setSubmitting(false)
    }
  }, [refreshOverview, selectedWorkflowId, taskForm])

  return useMemo(
    () => ({
      overview,
      selectedWorkflow,
      selectedWorkflowId,
      workflowForm,
      taskForm,
      loading,
      submitting,
      error,
      selectWorkflow,
      setWorkflowForm,
      setTaskForm,
      createWorkflow,
      createTask
    }),
    [
      createTask,
      createWorkflow,
      error,
      loading,
      overview,
      selectedWorkflow,
      selectedWorkflowId,
      selectWorkflow,
      submitting,
      taskForm,
      workflowForm
    ]
  )
}
