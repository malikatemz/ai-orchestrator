import React, { useEffect, useState } from 'react'
import Link from 'next/link'

import { SeoHead } from '../common/SeoHead'
import { orchestratorApi } from '../../services/orchestratorApi'
import type { AuditLogResponse, OpsMetricsResponse } from '../../types/orchestrator'

export function PlatformOpsPage() {
  const [metrics, setMetrics] = useState<OpsMetricsResponse | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const [nextMetrics, nextAuditLogs] = await Promise.all([orchestratorApi.getOpsMetrics(), orchestratorApi.getAuditLogs()])
        if (!active) {
          return
        }
        setMetrics(nextMetrics)
        setAuditLogs(nextAuditLogs)
      } catch (caughtError) {
        if (!active) {
          return
        }
        setError(caughtError instanceof Error ? caughtError.message : 'Unable to load platform ops')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      active = false
    }
  }, [])

  return (
    <>
      <SeoHead
        title="AI Orchestrator Platform Ops"
        description="Operational metrics, audit logs, failure hotspots, and execution lane visibility for AI Orchestrator."
        path="/platform-ops"
        noindex
      />

      <main className="marketing-shell">
        <header className="panel top-nav">
          <Link href="/" className="brand-mark">
            AI Orchestrator
          </Link>
          <nav className="top-links" aria-label="Platform">
            <Link href="/">Dashboard</Link>
            <Link href="/ai-operations-dashboard">Monitoring guide</Link>
            <Link href="/ai-agent-monitoring-checklist">Monitoring checklist</Link>
          </nav>
        </header>

        <section className="panel marketing-hero">
          <p className="eyebrow">Platform ops</p>
          <h1>Operational visibility for queues, failures, and audit events.</h1>
          <p className="lead">
            Use this view to monitor workflow volume, failure hotspots, execution lanes, and recent audit activity across the orchestrator.
          </p>
        </section>

        {error ? <p className="error-banner">{error}</p> : null}

        {loading ? (
          <section className="panel">
            <p className="muted">Loading platform ops data...</p>
          </section>
        ) : (
          <>
            <section className="stats-grid" aria-label="Platform ops metrics">
              <div className="panel stat-card">
                <p className="eyebrow">Workflows</p>
                <h3>{metrics?.workflows_total ?? 0}</h3>
                <p className="muted">Total orchestrated workflows</p>
              </div>
              <div className="panel stat-card">
                <p className="eyebrow">Tasks</p>
                <h3>{metrics?.tasks_total ?? 0}</h3>
                <p className="muted">Total tracked task executions</p>
              </div>
              <div className="panel stat-card">
                <p className="eyebrow">Failure rate</p>
                <h3>{metrics?.failure_rate ?? 0}%</h3>
                <p className="muted">Share of finished tasks that failed</p>
              </div>
              <div className="panel stat-card">
                <p className="eyebrow">Avg duration</p>
                <h3>{metrics?.average_duration_seconds ?? 0}s</h3>
                <p className="muted">Average completed task runtime</p>
              </div>
            </section>

            <section className="content-grid">
              <div className="stack">
                <section className="panel prose-card">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Execution lanes</p>
                      <h2>Queue distribution</h2>
                    </div>
                  </div>
                  <div className="recent-list">
                    {metrics?.execution_lanes.map((lane) => (
                      <div key={lane.queue_name} className="recent-item">
                        <strong>{lane.queue_name}</strong>
                        <span>{lane.tasks} tasks</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="panel prose-card">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Top failures</p>
                      <h2>Failing workflows</h2>
                    </div>
                  </div>
                  <div className="recent-list">
                    {metrics?.top_failing_workflows.map((workflow) => (
                      <div key={workflow.workflow_id} className="recent-item">
                        <strong>{workflow.workflow_name}</strong>
                        <span>{workflow.failed_tasks} failed tasks</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              <div className="stack">
                <section className="panel prose-card">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Recent failures</p>
                      <h2>Failure queue</h2>
                    </div>
                  </div>
                  <div className="recent-list">
                    {metrics?.recent_failures.map((task) => (
                      <div key={task.id} className="recent-item">
                        <strong>{task.name}</strong>
                        <span>{task.queue_name}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="panel prose-card">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Audit trail</p>
                      <h2>Recent audit events</h2>
                    </div>
                  </div>
                  <div className="recent-list">
                    {auditLogs.map((entry) => (
                      <div key={entry.id} className="recent-item">
                        <div>
                          <strong>{entry.event}</strong>
                          <p>{entry.actor}</p>
                        </div>
                        <span>{entry.resource_type}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </section>
          </>
        )}
      </main>
    </>
  )
}
