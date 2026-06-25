import { describe, expect, it } from 'vitest'

import { formatSimilarityScore } from './similarTitles'

describe('formatSimilarityScore', () => {
  it('rounds ratio to a percentage', () => {
    expect(formatSimilarityScore(0.8234)).toBe('82%')
    expect(formatSimilarityScore(1)).toBe('100%')
  })
})
