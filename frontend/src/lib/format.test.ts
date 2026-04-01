import { describe, expect, it } from 'vitest'

import { formatDate } from './format'

describe('formatDate', () => {
  it('returns a friendly fallback for empty values', () => {
    expect(formatDate(null)).toBe('No activity yet')
    expect(formatDate(undefined)).toBe('No activity yet')
  })

  it('formats valid timestamps into readable strings', () => {
    expect(formatDate('2024-01-01T00:00:00Z')).toContain('2024')
  })
})
