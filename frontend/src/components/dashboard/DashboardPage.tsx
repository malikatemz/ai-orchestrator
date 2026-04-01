import React from 'react'
import Link from 'next/link'

import { useDashboard } from '../../hooks/useDashboard'
import { API_BASE } from '../../lib/env'
import { SeoHead } from '../common/SeoHead'
import { AuthPanel } from './AuthPanel'
import { DemoPanel } from './DemoPanel'
import { ExecutionPanel } from './ExecutionPanel'
import { RecentActivity } from './RecentActivity'
import { SolutionPages } from './SolutionPages'
import { StatCard } from './StatCard'
import { WorkflowForm } from './WorkflowForm'
import { WorkflowRegistry } from './WorkflowRegistry'

export function DashboardPage() {
  const faqItems = [
    {
      question: 'What is an AI control plane?',
      answer:
        'An AI control plane is the operational layer that coordinates workflow routing, retries, execution states, and monitoring across AI systems.',
    },
    {
      question: 'How is this different from workflow orchestration software?',
      answer:
        'The homepage introduces the broader control plane, while the workflow orchestration page goes deeper on pipeline design, stage logic, and task routing.',
    },
    {
      question: 'How do teams monitor AI agents in production?',
      answer:
        'Teams combine health checks, execution logs, failure alerts, and dashboards to spot weak handoffs, repeated retries, and stuck work quickly.',
    },
  ]

  const {
    appConfig,
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
    createTask,
    retryTask,
    resetDemo,
  } = useDashboard()

  const workflows = overview?.workflows ?? []
  const recentTasks = overview?.recent_tasks ?? []

  return (
    <>
      <SeoHead
        title="AI Orchestrator | AI Control Plane for Production Workflows"
        description="AI Orchestrator is an AI control plane for routing tasks, monitoring execution, and improving reliability across production AI workflows."
        keywords="AI control plane, AI workflow dashboard, agent operations platform, AI reliability software, workflow monitoring"
        path="/"
        faqItems={faqItems}
      />

      <main className="shell">
        <nav className="section-nav panel" aria-label="Page sections">
          <a href="#platform-overview">Overview</a>
          <a href="#solution-pages">Solution Pages</a>
          <a href="#workflow-registry">Workflows</a>
          <a href="#execution-detail">Execution Detail</a>
          <a href="#recent-activity">Recent Activity</a>
          <Link href="/platform-ops">Platform Ops</Link>
        </nav>

        <section id="platform-overview" className="hero panel">
          <div>
            <p className="eyebrow">AI operations control plane</p>
            <h1>Ship orchestrated AI work with visibility, retries, and live execution context.</h1>
            <p className="lead">
              This dashboard turns the starter project into a working system: seeded workflows, health and overview APIs,
              execution queues, and a frontend that can monitor the whole loop.
            </p>
            <p className="lead compact">
              Use AI Orchestrator to coordinate task routing, retry behavior, and execution visibility across the AI
              systems your team depends on every day.
            </p>
          </div>
          <div className="hero-meta">
            <div>
              <span>API</span>
              <strong>{API_BASE}</strong>
            </div>
            <div>
              <span>Mode</span>
              <strong>{appConfig?.demo_mode ? 'Public demo' : appConfig?.auth_required ? 'Secured' : 'Local development'}</strong>
            </div>
            <div>
              <span>Selected workflow</span>
              <strong>{selectedWorkflow?.name || 'Waiting for data'}</strong>
            </div>
          </div>
        </section>

        <DemoPanel visible={Boolean(appConfig?.demo_mode)} canReset={Boolean(appConfig?.demo_seed_enabled)} disabled={submitting} onReset={() => void resetDemo()} />
        {appConfig?.auth_required ? <AuthPanel /> : null}

        {error ? <p className="error-banner">{error}</p> : null}

        {loading ? (
          <section className="panel">
            <p className="muted">Loading orchestrator state...</p>
          </section>
        ) : appConfig?.auth_required && !overview ? (
          <section className="panel prose-card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Secure mode</p>
                <h2>Authenticate to inspect workflows and dispatch tasks.</h2>
              </div>
            </div>
            <p>
              This environment requires a valid API token before workflow, task, and platform ops data can be loaded.
              Save the token above, then refresh the data views.
            </p>
          </section>
        ) : (
          <>
            <SolutionPages />

            <section className="panel prose-card">
              <div className="section-header">
                <div>
                  <p className="eyebrow">Platform overview</p>
                  <h2>What this site solves before you even touch the dashboard</h2>
                </div>
              </div>
              <p>
                AI Orchestrator is the control-plane layer for teams that need reliable routing, agent coordination,
                execution visibility, and operational oversight. Even if JavaScript is delayed or disabled, this page
                should still explain the core product, the main evaluation paths, and where to go next.
              </p>
              <p>
                The platform supports workflow design, task dispatching, agent-specific execution, and live monitoring.
                For a broader architecture view, visit <Link href="/ai-workflow-orchestration">AI workflow orchestration</Link>.
                For reliability oversight, see <Link href="/ai-operations-dashboard">AI operations dashboard</Link>. For
                examples, explore <Link href="/ai-workflow-automation-use-cases">workflow automation use cases</Link>.
              </p>
            </section>

            <section className="panel prose-card">
              <div className="section-header">
                <div>
                  <p className="eyebrow">Who it serves</p>
                  <h2>Common teams and production scenarios</h2>
                </div>
              </div>
              <div className="route-grid">
                <div className="route-card static-card">
                  <strong>Support operations</strong>
                  <span>Triage incidents, summarize escalations, and prepare customer-ready briefs.</span>
                </div>
                <div className="route-card static-card">
                  <strong>Platform engineering</strong>
                  <span>Standardize workflow execution, retries, and production observability for AI systems.</span>
                </div>
                <div className="route-card static-card">
                  <strong>Growth and lifecycle teams</strong>
                  <span>Coordinate planner, researcher, critic, and executor agents across repeatable experiments.</span>
                </div>
              </div>
            </section>

            <section className="stats-grid" aria-label="Platform metrics">
              <StatCard label="Workflows" value={overview?.metrics.workflows ?? 0} hint="Active orchestration pipelines" />
              <StatCard label="Tasks" value={overview?.metrics.tasks ?? 0} hint="Tracked executions across workflows" />
              <StatCard label="Running" value={overview?.metrics.running ?? 0} hint="Executions currently in flight" />
              <StatCard
                label="Success Rate"
                value={`${overview?.metrics.success_rate ?? 0}%`}
                hint={`${overview?.metrics.completed ?? 0} completed / ${overview?.metrics.failed ?? 0} failed`}
              />
            </section>

            <section className="content-grid">
              <div className="stack">
                <WorkflowRegistry workflows={workflows} selectedWorkflowId={selectedWorkflowId} onSelect={(workflowId) => void selectWorkflow(workflowId)} />
                <WorkflowForm value={workflowForm} disabled={submitting} onChange={setWorkflowForm} onSubmit={() => void createWorkflow()} />
              </div>

              <div className="stack">
                <ExecutionPanel
                  workflow={selectedWorkflow}
                  taskForm={taskForm}
                  disabled={submitting}
                  onTaskFormChange={setTaskForm}
                  onTaskSubmit={() => void createTask()}
                  onRetryTask={(taskId) => void retryTask(taskId)}
                />
                <RecentActivity tasks={recentTasks} />
              </div>
            </section>

            <section className="panel prose-card">
              <div className="section-header">
                <div>
                  <p className="eyebrow">FAQ</p>
                  <h2>Common evaluation questions</h2>
                </div>
              </div>
              <h3>What is AI workflow orchestration?</h3>
              <p>
                AI workflow orchestration is the process of coordinating prompts, agents, retries, and execution stages
                so AI work can run repeatedly with visibility and control.
              </p>
              <h3>How is this different from multi-agent orchestration?</h3>
              <p>
                Workflow orchestration focuses on the entire process, while{' '}
                <Link href="/multi-agent-orchestration">multi-agent orchestration</Link> focuses on how specialized agents
                collaborate inside that process.
              </p>
              <h3>How do teams monitor AI agents in production?</h3>
              <p>
                Teams typically combine health checks, execution logs, failure alerts, and dashboards. See the{' '}
                <Link href="/ai-agent-monitoring-checklist">AI agent monitoring checklist</Link> for a practical guide.
              </p>
            </section>
          </>
        )}
      </main>
    </>
  )
}
