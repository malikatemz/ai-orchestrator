import { describe, expect, it } from 'vitest'

import { buildCanonicalUrl } from './seo'

describe('buildCanonicalUrl', () => {
  it('joins the configured site url and route path', () => {
    expect(buildCanonicalUrl('/ai-workflow-orchestration')).toContain('/ai-workflow-orchestration')
  })

  it('supports the homepage path', () => {
    expect(buildCanonicalUrl('/')).toMatch(/\/$/)
  })
})
