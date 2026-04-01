import Link from 'next/link'

interface DemoPanelProps {
  visible: boolean
  canReset: boolean
  disabled: boolean
  onReset: () => void
}

export function DemoPanel({ visible, canReset, disabled, onReset }: DemoPanelProps) {
  if (!visible) {
    return null
  }

  return (
    <section className="panel prose-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">60-second demo</p>
          <h2>Show the value before you explain the architecture</h2>
        </div>
      </div>
      <p>
        This environment is running in public demo mode. Start with a seeded workflow, dispatch one new task, then retry
        a failed step to show how AI Orchestrator keeps execution visible and recoverable.
      </p>
      <div className="actions">
        {canReset ? (
          <button type="button" className="btn" disabled={disabled} onClick={onReset}>
            {disabled ? 'Resetting demo...' : 'Reset demo data'}
          </button>
        ) : null}
        <Link href="/platform-ops" className="btn btn-muted">
          View platform ops
        </Link>
      </div>
    </section>
  )
}
