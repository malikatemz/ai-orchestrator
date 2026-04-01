export interface RouteDefinition {
  href: string
  label: string
  description: string
}

export const marketingRoutes: RouteDefinition[] = [
  {
    href: '/',
    label: 'Platform Home',
    description: 'Live dashboard, workflow creation, and execution monitoring.'
  },
  {
    href: '/ai-workflow-orchestration',
    label: 'Workflow Orchestration',
    description: 'System design, task routing, retries, and process control.'
  },
  {
    href: '/multi-agent-orchestration',
    label: 'Multi-Agent Orchestration',
    description: 'Planner, researcher, critic, and executor coordination.'
  },
  {
    href: '/ai-operations-dashboard',
    label: 'AI Operations Dashboard',
    description: 'Monitoring, workflow health, recent activity, and execution oversight.'
  },
  {
    href: '/ai-workflow-automation-use-cases',
    label: 'Workflow Use Cases',
    description: 'Practical AI workflow automation examples for operations, support, and growth teams.'
  },
  {
    href: '/ai-agent-monitoring-checklist',
    label: 'Agent Monitoring Checklist',
    description: 'A practical checklist for monitoring AI agents, task reliability, and production operations.'
  }
]

export const appRoutes: RouteDefinition[] = [
  {
    href: '/platform-ops',
    label: 'Platform Ops',
    description: 'Operational metrics, audit logs, queue lanes, and failure hotspots across the orchestrator.'
  }
]

export const coreRoutes: RouteDefinition[] = [...marketingRoutes, ...appRoutes]
export const crawlableRoutes: RouteDefinition[] = [...marketingRoutes]
