import { describe, expect, it } from 'vitest'

import { buildCanonicalUrl, buildFaqSchema, buildRobotsContent, isIndexableSiteUrl } from './seo'

describe('buildCanonicalUrl', () => {
  it('joins the configured site url and route path when the site url is indexable', () => {
    expect(buildCanonicalUrl('/ai-workflow-orchestration', 'https://aiorchestrator.dev')).toBe(
      'https://aiorchestrator.dev/ai-workflow-orchestration',
    )
  })

  it('supports the homepage path', () => {
    expect(buildCanonicalUrl('/', 'https://aiorchestrator.dev')).toBe('https://aiorchestrator.dev/')
  })

  it('treats placeholder hosts as non-indexable', () => {
    expect(isIndexableSiteUrl('https://example.com')).toBe(false)
    expect(isIndexableSiteUrl('http://localhost:3000')).toBe(false)
  })

  it('switches to noindex robots when the site url is not safe for indexing', () => {
    expect(buildRobotsContent(false, 'https://example.com')).toBe('noindex,follow,max-image-preview:large')
    expect(buildRobotsContent(true)).toBe('noindex,follow,max-image-preview:large')
  })

  it('builds FAQ schema for pages with structured questions', () => {
    const schema = buildFaqSchema(
      [{ question: 'What is AI orchestration?', answer: 'A control layer for AI workflows.' }],
      'https://aiorchestrator.dev',
    )
    expect(schema?.['@type']).toBeTypeOf('string')
  })
})
