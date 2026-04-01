import type { ChangeEvent, FormEvent } from 'react'

import type { WorkflowFormValues } from '../../types/orchestrator'

interface WorkflowFormProps {
  value: WorkflowFormValues
  disabled: boolean
  onChange: (value: WorkflowFormValues) => void
  onSubmit: () => void
}

export function WorkflowForm({ value, disabled, onChange, onSubmit }: WorkflowFormProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit()
  }

  function update<K extends keyof WorkflowFormValues>(key: K, nextValue: WorkflowFormValues[K]) {
    onChange({ ...value, [key]: nextValue })
  }

  return (
    <section className="panel" aria-label="Create workflow">
      <div className="section-header">
        <div>
          <p className="eyebrow">Create workflow</p>
          <h2>Launch a new pipeline</h2>
        </div>
      </div>
      <form className="form-grid" onSubmit={handleSubmit}>
        <input value={value.name} onChange={(event: ChangeEvent<HTMLInputElement>) => update('name', event.target.value)} placeholder="Workflow name" required />
        <input value={value.owner} onChange={(event: ChangeEvent<HTMLInputElement>) => update('owner', event.target.value)} placeholder="Owner" required />
        <select value={value.priority} onChange={(event: ChangeEvent<HTMLSelectElement>) => update('priority', event.target.value as WorkflowFormValues['priority'])}>
          <option value="low">Low priority</option>
          <option value="medium">Medium priority</option>
          <option value="high">High priority</option>
          <option value="critical">Critical priority</option>
        </select>
        <input
          value={value.target_model}
          onChange={(event: ChangeEvent<HTMLInputElement>) => update('target_model', event.target.value)}
          placeholder="Target model"
          required
        />
        <textarea
          value={value.description}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => update('description', event.target.value)}
          placeholder="Describe the automation objective, guardrails, and intended outcome"
          rows={4}
          required
        />
        <button type="submit" className="primary-button" disabled={disabled}>
          {disabled ? 'Saving...' : 'Create workflow'}
        </button>
      </form>
    </section>
  )
}
