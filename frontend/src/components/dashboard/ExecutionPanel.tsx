import type { ChangeEvent, FormEvent } from 'react'

import { formatDate } from '../../lib/format'
import type { TaskFormValues, WorkflowDetail } from '../../types/orchestrator'

interface ExecutionPanelProps {
  workflow: WorkflowDetail | null
  taskForm: TaskFormValues
  disabled: boolean
  onTaskFormChange: (value: TaskFormValues) => void
  onTaskSubmit: () => void
}

export function ExecutionPanel({ workflow, taskForm, disabled, onTaskFormChange, onTaskSubmit }: ExecutionPanelProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onTaskSubmit()
  }

  function update<K extends keyof TaskFormValues>(key: K, nextValue: TaskFormValues[K]) {
    onTaskFormChange({ ...taskForm, [key]: nextValue })
  }

  return (
    <section id="execution-detail" className="panel detail-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Execution detail</p>
          <h2>{workflow?.name || 'Select a workflow'}</h2>
        </div>
        {workflow ? <span className="pill neutral">{workflow.target_model}</span> : null}
      </div>

      {workflow ? (
        <>
          <p className="lead compact">{workflow.description}</p>
          <div className="detail-grid">
            <div>
              <span className="detail-label">Owner</span>
              <strong>{workflow.owner}</strong>
            </div>
            <div>
              <span className="detail-label">Priority</span>
              <strong>{workflow.priority}</strong>
            </div>
            <div>
              <span className="detail-label">Last run</span>
              <strong>{formatDate(workflow.last_run_at)}</strong>
            </div>
            <div>
              <span className="detail-label">Updated</span>
              <strong>{formatDate(workflow.updated_at)}</strong>
            </div>
          </div>

          <form className="form-grid" onSubmit={handleSubmit}>
            <input value={taskForm.name} onChange={(event: ChangeEvent<HTMLInputElement>) => update('name', event.target.value)} placeholder="Task name" required />
            <select value={taskForm.agent} onChange={(event: ChangeEvent<HTMLSelectElement>) => update('agent', event.target.value as TaskFormValues['agent'])}>
              <option value="planner">Planner agent</option>
              <option value="researcher">Researcher agent</option>
              <option value="critic">Critic agent</option>
              <option value="executor">Executor agent</option>
            </select>
            <textarea
              value={taskForm.input}
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) => update('input', event.target.value)}
              placeholder="Describe the work item, constraints, and desired result"
              rows={5}
              required
            />
            <button type="submit" className="primary-button" disabled={disabled}>
              {disabled ? 'Dispatching...' : 'Dispatch task'}
            </button>
          </form>

          <div className="task-list">
            {workflow.tasks.map((task) => (
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
  )
}
