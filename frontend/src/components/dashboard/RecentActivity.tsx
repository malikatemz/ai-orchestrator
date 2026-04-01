import { formatDate } from '../../lib/format'
import type { TaskResponse } from '../../types/orchestrator'

interface RecentActivityProps {
  tasks: TaskResponse[]
}

export function RecentActivity({ tasks }: RecentActivityProps) {
  return (
    <section id="recent-activity" className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Recent activity</p>
          <h2>Cross-system queue</h2>
        </div>
      </div>
      <div className="recent-list">
        {tasks.map((task) => (
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
  )
}
