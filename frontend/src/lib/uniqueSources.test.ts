import { describe, expect, it } from 'vitest'
import type { Source } from '../types'
import { downloadableDocIds, uniqueSourcesByDoc } from './uniqueSources'

describe('uniqueSourcesByDoc', () => {
  it('collapses chunks from the same doc_id and keeps section labels', () => {
    const sources: Source[] = [
      { doc_id: 'a', filename: 'Roof.pdf', section: 'ROOF', source_type: 'google_drive' },
      { doc_id: 'a', filename: 'Roof.pdf', section: 'EXTERIOR', source_type: 'google_drive' },
      { doc_id: 'b', filename: 'Other.pdf', section: 'INTRO', source_type: 'google_drive' },
    ]
    const unique = uniqueSourcesByDoc(sources)
    expect(unique).toHaveLength(2)
    expect(unique[0].docId).toBe('a')
    expect(unique[0].sections).toEqual(['ROOF', 'EXTERIOR'])
    expect(unique[0].downloadable).toBe(true)
    expect(unique[1].docId).toBe('b')
    expect(downloadableDocIds(unique)).toEqual(['a', 'b'])
  })

  it('marks rows without doc_id as not downloadable', () => {
    const sources: Source[] = [
      { filename: 'legacy.pdf', section: 'NOTES' },
      { doc_id: '  ', filename: 'blank-id.pdf' },
    ]
    const unique = uniqueSourcesByDoc(sources)
    expect(unique).toHaveLength(2)
    expect(unique.every(u => !u.downloadable)).toBe(true)
    expect(downloadableDocIds(unique)).toEqual([])
  })
})
