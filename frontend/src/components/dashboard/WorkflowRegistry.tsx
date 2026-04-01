import React from 'react'
import type { WorkflowSummary } from '../../types/orchestrator'

interface WorkflowRegistryProps {
  workflows: WorkflowSummary[]
  selectedWorkflowId: number | null
  onSelect: (workflowId: number) => void
}

export function WorkflowRegistry({ workflows, selectedWorkflowId, onSelect }: WorkflowRegistryProps) {
  return (
    <section id="workflow-registry" className="panel">
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
            className={`workflow-card ${selectedWorkflowId === workflow.id ? 'is-active' : ''}`}
            onClick={() => onSelect(workflow.id)}
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
  )
}
