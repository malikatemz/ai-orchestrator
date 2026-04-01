import React from 'react'
import Link from 'next/link'
import type { ReactNode } from 'react'

export interface MarketingPageContent {
  title: string
  description: string
  path: string
  eyebrow: string
  heading: string
  intro: string
  body: ReactNode
}

export const marketingPages: Record<
  'workflow' | 'multiAgent' | 'operations' | 'useCases' | 'monitoringChecklist',
  MarketingPageContent
> = {
  workflow: {
    title: 'AI Workflow Orchestration Software | AI Orchestrator',
    description:
      'AI workflow orchestration software for designing, monitoring, and scaling reliable AI pipelines with retries, visibility, and execution control.',
    path: '/ai-workflow-orchestration',
    eyebrow: 'Workflow orchestration',
    heading: 'AI workflow orchestration for teams that need reliability, not just demos.',
    intro:
      'Design repeatable AI workflows, route tasks between agents, and monitor execution from a control plane that helps operations, product, and engineering teams ship with more confidence.',
    body: (
      <>
        <section className="content-grid marketing-grid">
          <article className="panel prose-card">
            <h2>What AI workflow orchestration should solve</h2>
            <p>
              AI workflow orchestration is the system design layer for production AI work. It is where teams define the
              sequence of steps, the conditions for moving between them, the retry logic, and the ownership model that
              keeps an automated process understandable in production.
            </p>
            <p>
              AI Orchestrator is built around that control layer. You can define workflows, dispatch tasks, inspect
              recent activity, and keep execution state visible across the pipeline without reducing everything to a
              single prompt chain.
            </p>
          </article>

          <article className="panel prose-card">
            <h2>Who this page is for</h2>
            <ul className="prose-list">
              <li>Product teams building repeatable AI pipeline logic.</li>
              <li>Platform teams standardizing how AI tasks are executed and monitored.</li>
              <li>Operations teams that need auditability instead of black-box automation.</li>
            </ul>
          </article>
        </section>

        <section className="panel prose-card">
          <h2>Core workflow orchestration capabilities</h2>
          <div className="route-grid">
            <div className="route-card static-card">
              <strong>Workflow registry</strong>
              <span>Track orchestration pipelines with ownership, priority, and model targeting.</span>
            </div>
            <div className="route-card static-card">
              <strong>Task lifecycle control</strong>
              <span>See pending, running, completed, and failed execution states with retries.</span>
            </div>
            <div className="route-card static-card">
              <strong>Operational visibility</strong>
              <span>Monitor recent activity, task output, and execution durations in one place.</span>
            </div>
          </div>
        </section>

        <section className="panel prose-card">
          <h2>What belongs on other pages</h2>
          <p>
            If your main problem is coordinating specialized agents, see the{' '}
            <Link href="/multi-agent-orchestration">multi-agent orchestration page</Link>. If your main problem is live
            monitoring and reliability oversight, see the <Link href="/ai-operations-dashboard">AI operations dashboard page</Link>.
            If you want concrete implementation ideas, browse the{' '}
            <Link href="/ai-workflow-automation-use-cases">workflow automation use cases</Link>.
          </p>
        </section>

        <section className="panel prose-card">
          <h2>Implementation checklist for workflow teams</h2>
          <ul className="prose-list">
            <li>Define workflow stages before assigning model or agent roles.</li>
            <li>Track ownership, retry policy, and status transitions per workflow.</li>
            <li>Measure success at the workflow level, not only per individual task.</li>
            <li>
              Pair workflow design with an <Link href="/ai-agent-monitoring-checklist">agent monitoring checklist</Link>{' '}
              before production rollout.
            </li>
          </ul>
        </section>

        <section className="panel prose-card">
          <h2>When this page should rank</h2>
          <p>
            This page is designed for workflow orchestration intent: teams evaluating how to structure AI pipelines,
            govern task flow, and make automated execution reliable enough for real operations.
          </p>
        </section>
      </>
    )
  },
  multiAgent: {
    title: 'Multi-Agent Orchestration Platform | AI Orchestrator',
    description:
      'Coordinate planner, researcher, critic, and executor agents with a multi-agent orchestration platform built for visibility, control, and reliable handoffs.',
    path: '/multi-agent-orchestration',
    eyebrow: 'Agent coordination',
    heading: 'Multi-agent orchestration with clearer handoffs, better visibility, and less operational guesswork.',
    intro:
      'Use a single orchestration layer to coordinate specialized AI agents, inspect their outputs, and keep every stage of execution visible from request to result.',
    body: (
      <>
        <section className="content-grid marketing-grid">
          <article className="panel prose-card">
            <h2>Why multi-agent systems break down</h2>
            <p>
              Most multi-agent setups fail at the seams. One agent produces output another agent cannot reliably use, or
              teams lose track of who handled what and when. The problem is usually the handoff contract between roles,
              not the raw model quality in isolation.
            </p>
            <p>
              AI Orchestrator gives each task an agent role, a status, a stage, and a visible execution trail so agent
              collaboration becomes easier to inspect and improve.
            </p>
          </article>

          <article className="panel prose-card">
            <h2>Agent patterns supported by the current system</h2>
            <ul className="prose-list">
              <li>Planner agents for workflow design and next-step sequencing.</li>
              <li>Researcher agents for evidence gathering and synthesis.</li>
              <li>Critic agents for review, QA, and challenge passes.</li>
              <li>Executor agents for final action-oriented outputs.</li>
            </ul>
          </article>
        </section>

        <section className="panel prose-card">
          <h2>How to structure multi-agent orchestration</h2>
          <p>
            Start with a workflow that defines the outcome, assign the first task to the right agent, and use explicit
            task output to inform the next handoff. The dashboard makes those transitions visible, which helps reduce
            silent failure between agent stages.
          </p>
          <p>
            Teams using multiple agent roles often also need stronger workflow-level controls. For that broader view, visit{' '}
            <Link href="/ai-workflow-orchestration">AI workflow orchestration</Link>.
          </p>
        </section>

        <section className="panel prose-card">
          <h2>Multi-agent design guardrails</h2>
          <ul className="prose-list">
            <li>Define what each agent is responsible for before tuning prompts.</li>
            <li>Keep intermediate outputs inspectable so reviewers can spot weak handoffs.</li>
            <li>Track task stages to understand where coordination breaks down.</li>
            <li>
              Use an <Link href="/ai-agent-monitoring-checklist">agent monitoring checklist</Link> to catch repeated
              failure patterns across agent roles.
            </li>
          </ul>
        </section>

        <section className="panel prose-card">
          <h2>Best next page by intent</h2>
          <p>
            If you are evaluating operational monitoring and execution oversight, go to the{' '}
            <Link href="/ai-operations-dashboard">AI operations dashboard page</Link>. If you want the broader system
            architecture view, return to the <Link href="/">platform home</Link>. If you want examples of how teams put
            coordinated agents to work, review the <Link href="/ai-workflow-automation-use-cases">workflow automation use cases</Link>.
          </p>
        </section>
      </>
    )
  },
  operations: {
    title: 'AI Operations Dashboard | Monitor AI Workflows | AI Orchestrator',
    description:
      'An AI operations dashboard for monitoring workflow health, recent task activity, execution status, and reliability signals across your AI system.',
    path: '/ai-operations-dashboard',
    eyebrow: 'Operations visibility',
    heading: 'An AI operations dashboard for monitoring workflow health and execution in real time.',
    intro:
      'Track active workflows, recent task activity, completion status, failures, and execution details from a dashboard designed for AI operations teams and platform owners.',
    body: (
      <>
        <section className="content-grid marketing-grid">
          <article className="panel prose-card">
            <h2>What an AI operations dashboard should show</h2>
            <p>
              A useful AI operations dashboard should surface workflow counts, task health, running work, failure signals,
              and recent execution activity without forcing teams to read raw logs first.
            </p>
            <p>
              The current AI Orchestrator dashboard already exposes workflow summaries, success rate, recent activity, and
              execution details for selected workflows.
            </p>
          </article>

          <article className="panel prose-card">
            <h2>Operational outcomes teams care about</h2>
            <ul className="prose-list">
              <li>Faster detection of failed or stuck AI tasks.</li>
              <li>Clearer reporting on which workflows are active and who owns them.</li>
              <li>Lower time-to-debug when an execution chain produces weak output.</li>
            </ul>
          </article>
        </section>

        <section className="panel prose-card">
          <h2>Operational monitoring checklist</h2>
          <ul className="prose-list">
            <li>Watch failure rate, queue depth, and long-running execution counts.</li>
            <li>Track recent activity by workflow owner so incidents are easier to route.</li>
            <li>Use task detail views to inspect execution history before diving into raw logs.</li>
            <li>
              Pair dashboards with the <Link href="/ai-agent-monitoring-checklist">agent monitoring checklist</Link> for
              a repeatable production review process.
            </li>
          </ul>
        </section>

        <section className="panel prose-card">
          <h2>Where this fits in the site structure</h2>
          <p>
            This page targets dashboard and monitoring intent. It is intentionally different from{' '}
            <Link href="/ai-workflow-orchestration">AI workflow orchestration</Link>, which targets system design and
            process control intent, and from <Link href="/multi-agent-orchestration">multi-agent orchestration</Link>,
            which targets agent coordination intent.
          </p>
        </section>

        <section className="panel prose-card">
          <h2>See the live product surface</h2>
          <p>
            The interactive dashboard lives on the <Link href="/">platform home</Link>, where you can inspect workflows,
            task states, and recent execution activity directly.
          </p>
        </section>
      </>
    )
  },
  useCases: {
    title: 'AI Workflow Automation Use Cases | AI Orchestrator',
    description:
      'Practical AI workflow automation use cases for support, operations, lifecycle, and internal platform teams evaluating production-ready orchestration.',
    path: '/ai-workflow-automation-use-cases',
    eyebrow: 'Use cases',
    heading: 'AI workflow automation use cases teams can actually operationalize.',
    intro:
      'Explore concrete AI workflow automation patterns for support, operations, and growth teams that need repeatable execution, visible task states, and easier production debugging.',
    body: (
      <>
        <section className="content-grid marketing-grid">
          <article className="panel prose-card">
            <h2>Support operations</h2>
            <p>
              Route incoming cases through a triage workflow, assign a researcher agent to collect account context, send
              a critic agent through the draft response, and let an executor prepare the final handoff for a human reviewer.
            </p>
          </article>

          <article className="panel prose-card">
            <h2>Growth and lifecycle campaigns</h2>
            <p>
              Use planner, researcher, and executor stages to generate campaign ideas, validate audience fit, and package
              final assets while keeping every stage visible for review.
            </p>
          </article>
        </section>

        <section className="content-grid marketing-grid">
          <article className="panel prose-card">
            <h2>Internal operations</h2>
            <p>
              Automate recurring ops work such as incident summaries, change-log rollups, or weekly status digests with
              workflows that make retries and task ownership explicit.
            </p>
          </article>

          <article className="panel prose-card">
            <h2>Platform enablement</h2>
            <p>
              Standardize how AI requests are dispatched across teams by putting them through a common workflow layer
              instead of letting every team build private one-off automations.
            </p>
          </article>
        </section>

        <section className="panel prose-card">
          <h2>How to evaluate a use case before launch</h2>
          <ul className="prose-list">
            <li>Check whether the workflow has a clear owner and success metric.</li>
            <li>Make sure each handoff can be inspected and retried.</li>
            <li>Confirm the work is frequent enough to benefit from orchestration.</li>
            <li>
              Tie the rollout back to <Link href="/ai-workflow-orchestration">workflow orchestration</Link> design and{' '}
              <Link href="/ai-operations-dashboard">operations dashboard</Link> monitoring.
            </li>
          </ul>
        </section>

        <section className="panel prose-card">
          <h2>Related pages</h2>
          <p>
            This page targets solution and use-case intent. For system design, go to{' '}
            <Link href="/ai-workflow-orchestration">AI workflow orchestration</Link>. For agent coordination patterns,
            go to <Link href="/multi-agent-orchestration">multi-agent orchestration</Link>. For production oversight, use
            the <Link href="/ai-agent-monitoring-checklist">agent monitoring checklist</Link>.
          </p>
        </section>
      </>
    )
  },
  monitoringChecklist: {
    title: 'AI Agent Monitoring Checklist | AI Orchestrator',
    description:
      'A practical AI agent monitoring checklist covering task states, failures, retries, ownership, observability, and dashboard signals for production teams.',
    path: '/ai-agent-monitoring-checklist',
    eyebrow: 'Monitoring checklist',
    heading: 'An AI agent monitoring checklist for teams running workflows in production.',
    intro:
      'Use this checklist to review reliability, alerting, retry behavior, and execution visibility before your AI workflows become business-critical dependencies.',
    body: (
      <>
        <section className="panel prose-card">
          <h2>Core checklist</h2>
          <ul className="prose-list">
            <li>Every workflow has an owner and an escalation path.</li>
            <li>Every task has a visible status, stage, and timestamp.</li>
            <li>Retries are explicit and measured instead of silently looping.</li>
            <li>Recent failures can be inspected without querying raw infrastructure logs first.</li>
            <li>Long-running work and stuck tasks are easy to identify in the dashboard.</li>
          </ul>
        </section>

        <section className="content-grid marketing-grid">
          <article className="panel prose-card">
            <h2>Signals to watch</h2>
            <ul className="prose-list">
              <li>Failure rate by workflow and agent role.</li>
              <li>Queue age or task duration spikes.</li>
              <li>Repeated retries for the same stage.</li>
              <li>Changes in completion rate after deploys.</li>
            </ul>
          </article>

          <article className="panel prose-card">
            <h2>Questions for every incident review</h2>
            <ul className="prose-list">
              <li>Did the workflow fail because of orchestration, prompt quality, or dependency issues?</li>
              <li>Was the handoff between agents inspectable enough to debug quickly?</li>
              <li>Did alerting point the team to the right owner?</li>
              <li>Can this failure mode be turned into a repeatable rule or retry policy?</li>
            </ul>
          </article>
        </section>

        <section className="panel prose-card">
          <h2>Where this checklist fits</h2>
          <p>
            This page targets monitoring intent. It complements <Link href="/ai-operations-dashboard">AI operations dashboard</Link>{' '}
            content, but it is more tactical and review-oriented. For broader system design, go back to{' '}
            <Link href="/ai-workflow-orchestration">AI workflow orchestration</Link>. For practical rollout examples,
            read the <Link href="/ai-workflow-automation-use-cases">workflow automation use cases</Link>.
          </p>
        </section>
      </>
    )
  }
}
