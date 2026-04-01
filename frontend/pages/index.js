import { useEffect, useMemo, useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

const emptyWorkflow = {
  name: '',
  description: '',
  owner: 'operations',
  priority: 'medium',
  target_model: 'gpt-4.1-mini'
}

const emptyTask = {
  name: '',
  input: '',
  agent: 'planner'
}

function formatDate(value) {
  if (!value) return 'No activity yet'
  return new Date(value).toLocaleString()
}

function StatCard({ label, value, hint }) {
  return (
    <div className="panel stat-card">
      <p className="eyebrow">{label}</p>
      <h3>{value}</h3>
      <p className="muted">{hint}</p>
    </div>
  )
}

export default function Home() {
  const [overview, setOverview] = useState(null)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(null)
  const [selectedWorkflow, setSelectedWorkflow] = useState(null)
  const [workflowForm, setWorkflowForm] = useState(emptyWorkflow)
  const [taskForm, setTaskForm] = useState(emptyTask)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const workflows = overview?.workflows || []
  const recentTasks = overview?.recent_tasks || []
  const selectedFallback = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedWorkflowId) || workflows[0] || null,
    [selectedWorkflowId, workflows]
  )

  async function fetchOverview(nextSelectedId) {
    const response = await fetch(`${API_BASE}/overview`)
    if (!response.ok) {
      throw new Error('Unable to load overview')
    }

    const data = await response.json()
    setOverview(data)

    const preferredId = nextSelectedId || selectedWorkflowId || data.workflows?.[0]?.id
    if (preferredId) {
      setSelectedWorkflowId(preferredId)
      await fetchWorkflow(preferredId)
    } else {
      setSelectedWorkflow(null)
    }
  }

  async function fetchWorkflow(workflowId) {
    const response = await fetch(`${API_BASE}/workflows/${workflowId}`)
    if (!response.ok) {
      throw new Error('Unable to load workflow details')
    }
    const data = await response.json()
    setSelectedWorkflow(data)
  }

  useEffect(() => {
    let active = true

    async function boot() {
      try {
        if (!active) return
        await fetchOverview()
      } catch (err) {
        if (active) setError(err.message)
      } finally {
        if (active) setLoading(false)
      }
    }

    boot()
    const interval = setInterval(() => {
      fetchOverview().catch((err) => setError(err.message))
    }, 5000)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [selectedWorkflowId])

  async function handleCreateWorkflow(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflowForm)
      })

      if (!response.ok) {
        throw new Error('Workflow creation failed')
      }

      const workflow = await response.json()
      setWorkflowForm(emptyWorkflow)
      await fetchOverview(workflow.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCreateTask(event) {
    event.preventDefault()
    if (!selectedWorkflowId) return

    setSubmitting(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE}/workflows/${selectedWorkflowId}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(taskForm)
      })

      if (!response.ok) {
        throw new Error('Task dispatch failed')
      }

      setTaskForm(emptyTask)
      await fetchOverview(selectedWorkflowId)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="shell">
      <section className="hero panel">
        <div>
          <p className="eyebrow">AI operations control plane</p>
          <h1>Ship orchestrated AI work with visibility, retries, and live execution context.</h1>
          <p className="lead">
            This dashboard turns the starter project into a working system: seeded workflows, health and overview APIs,
            execution queues, and a frontend that can monitor the whole loop.
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span>API</span>
            <strong>{API_BASE}</strong>
          </div>
          <div>
            <span>Selected workflow</span>
            <strong>{selectedFallback?.name || 'Waiting for data'}</strong>
          </div>
        </div>
      </section>

      {error ? <p className="error-banner">{error}</p> : null}

      {loading ? (
        <section className="panel">
          <p className="muted">Loading orchestrator state...</p>
        </section>
      ) : (
        <>
          <section className="stats-grid">
            <StatCard label="Workflows" value={overview?.metrics.workflows || 0} hint="Active orchestration pipelines" />
            <StatCard label="Tasks" value={overview?.metrics.tasks || 0} hint="Tracked executions across workflows" />
            <StatCard label="Running" value={overview?.metrics.running || 0} hint="Executions currently in flight" />
            <StatCard
              label="Success Rate"
              value={`${overview?.metrics.success_rate || 0}%`}
              hint={`${overview?.metrics.completed || 0} completed / ${overview?.metrics.failed || 0} failed`}
            />
          </section>

          <section className="content-grid">
            <div className="stack">
              <section className="panel">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Workflow registry</p>
                    <h2>Production lanes</h2>
                  </div>
                  <span className="pill">{workflows.length} total</span>
                </div>
                <div className="workflow-list">
                  {workflows.map((workflow) => (
                    <button
                      type="button"
                      key={workflow.id}
                      className={`workflow-card ${selectedFallback?.id === workflow.id ? 'is-active' : ''}`}
                      onClick={() => {
                        setSelectedWorkflowId(workflow.id)
                        fetchWorkflow(workflow.id).catch((err) => setError(err.message))
                      }}
                    >
                      <div className="workflow-topline">
                        <span className={`pill priority-${workflow.priority}`}>{workflow.priority}</span>
                        <span className="pill neutral">{workflow.owner}</span>
                      </div>
                      <h3>{workflow.name}</h3>
                      <p>{workflow.description}</p>
                      <div className="workflow-metrics">
                        <span>{workflow.task_count} tasks</span>
                        <span>{workflow.completed_tasks} complete</span>
                        <span>{workflow.active_tasks} active</span>
                      </div>
                    </button>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Create workflow</p>
                    <h2>Launch a new pipeline</h2>
                  </div>
                </div>
                <form className="form-grid" onSubmit={handleCreateWorkflow}>
                  <input
                    value={workflowForm.name}
                    onChange={(event) => setWorkflowForm({ ...workflowForm, name: event.target.value })}
                    placeholder="Workflow name"
                    required
                  />
                  <input
                    value={workflowForm.owner}
                    onChange={(event) => setWorkflowForm({ ...workflowForm, owner: event.target.value })}
                    placeholder="Owner"
                    required
                  />
                  <select
                    value={workflowForm.priority}
                    onChange={(event) => setWorkflowForm({ ...workflowForm, priority: event.target.value })}
                  >
                    <option value="low">Low priority</option>
                    <option value="medium">Medium priority</option>
                    <option value="high">High priority</option>
                    <option value="critical">Critical priority</option>
                  </select>
                  <input
                    value={workflowForm.target_model}
                    onChange={(event) => setWorkflowForm({ ...workflowForm, target_model: event.target.value })}
                    placeholder="Target model"
                    required
                  />
                  <textarea
                    value={workflowForm.description}
                    onChange={(event) => setWorkflowForm({ ...workflowForm, description: event.target.value })}
                    placeholder="Describe the automation objective, guardrails, and intended outcome"
                    rows={4}
                    required
                  />
                  <button type="submit" className="primary-button" disabled={submitting}>
                    {submitting ? 'Saving...' : 'Create workflow'}
                  </button>
                </form>
              </section>
            </div>

            <div className="stack">
              <section className="panel detail-panel">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Execution detail</p>
                    <h2>{selectedWorkflow?.name || 'Select a workflow'}</h2>
                  </div>
                  {selectedWorkflow ? <span className="pill neutral">{selectedWorkflow.target_model}</span> : null}
                </div>

                {selectedWorkflow ? (
                  <>
                    <p className="lead compact">{selectedWorkflow.description}</p>
                    <div className="detail-grid">
                      <div>
                        <span className="detail-label">Owner</span>
                        <strong>{selectedWorkflow.owner}</strong>
                      </div>
                      <div>
                        <span className="detail-label">Priority</span>
                        <strong>{selectedWorkflow.priority}</strong>
                      </div>
                      <div>
                        <span className="detail-label">Last run</span>
                        <strong>{formatDate(selectedWorkflow.last_run_at)}</strong>
                      </div>
                      <div>
                        <span className="detail-label">Updated</span>
                        <strong>{formatDate(selectedWorkflow.updated_at)}</strong>
                      </div>
                    </div>

                    <form className="form-grid" onSubmit={handleCreateTask}>
                      <input
                        value={taskForm.name}
                        onChange={(event) => setTaskForm({ ...taskForm, name: event.target.value })}
                        placeholder="Task name"
                        required
                      />
                      <select
                        value={taskForm.agent}
                        onChange={(event) => setTaskForm({ ...taskForm, agent: event.target.value })}
                      >
                        <option value="planner">Planner agent</option>
                        <option value="researcher">Researcher agent</option>
                        <option value="critic">Critic agent</option>
                        <option value="executor">Executor agent</option>
                      </select>
                      <textarea
                        value={taskForm.input}
                        onChange={(event) => setTaskForm({ ...taskForm, input: event.target.value })}
                        placeholder="Describe the work item, constraints, and desired result"
                        rows={5}
                        required
                      />
                      <button type="submit" className="primary-button" disabled={submitting}>
                        {submitting ? 'Dispatching...' : 'Dispatch task'}
                      </button>
                    </form>

                    <div className="task-list">
                      {selectedWorkflow.tasks.map((task) => (
                        <article key={task.id} className="task-card">
                          <div className="task-header">
                            <div>
                              <h3>{task.name}</h3>
                              <p>{task.agent} agent</p>
                            </div>
                            <div className="task-pills">
                              <span className={`pill status-${task.status}`}>{task.status}</span>
                              <span className="pill neutral">{task.stage}</span>
                            </div>
                          </div>
                          <p className="task-copy">{task.input}</p>
                          <p className="muted">{task.output || 'Awaiting output from the orchestration worker.'}</p>
                          <div className="task-footer">
                            <span>Retries: {task.retries}</span>
                            <span>Duration: {task.duration_seconds ? `${task.duration_seconds}s` : 'Pending'}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="muted">No workflow selected yet.</p>
                )}
              </section>

              <section className="panel">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Recent activity</p>
                    <h2>Cross-system queue</h2>
                  </div>
                </div>
                <div className="recent-list">
                  {recentTasks.map((task) => (
                    <div key={task.id} className="recent-item">
                      <div>
                        <strong>{task.name}</strong>
                        <p>{formatDate(task.created_at)}</p>
                      </div>
                      <span className={`pill status-${task.status}`}>{task.status}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </section>
        </>
      )}
    </main>
  )
}
