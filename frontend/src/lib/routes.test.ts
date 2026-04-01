import { describe, expect, it } from 'vitest'

import { appRoutes, coreRoutes, crawlableRoutes, marketingRoutes } from './routes'

describe('coreRoutes', () => {
  it('includes the homepage, marketing routes, and app routes', () => {
    expect(coreRoutes.map((route) => route.href)).toEqual([
      '/',
      '/ai-workflow-orchestration',
      '/multi-agent-orchestration',
      '/ai-operations-dashboard',
      '/ai-workflow-automation-use-cases',
      '/ai-agent-monitoring-checklist',
      '/platform-ops',
    ])
  })

  it('provides a label and description for each route', () => {
    coreRoutes.forEach((route) => {
      expect(route.label.length).toBeGreaterThan(0)
      expect(route.description.length).toBeGreaterThan(0)
    })
  })

  it('keeps crawlable routes limited to the public marketing cluster', () => {
    expect(marketingRoutes.map((route) => route.href)).toEqual([
      '/',
      '/ai-workflow-orchestration',
      '/multi-agent-orchestration',
      '/ai-operations-dashboard',
      '/ai-workflow-automation-use-cases',
      '/ai-agent-monitoring-checklist',
    ])
    expect(crawlableRoutes).toEqual(marketingRoutes)
    expect(appRoutes.map((route) => route.href)).toEqual(['/platform-ops'])
  })
})
