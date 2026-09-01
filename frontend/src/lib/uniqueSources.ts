import type { Source } from '../types'

export type UniqueSource = {
  docId: string
  filename: string
  source_url?: string
  source_type?: string
  source?: string
  sections: string[]
  downloadable: boolean
}

/** Collapse citation rows into one entry per document, preserving section labels. */
export function uniqueSourcesByDoc(sources: Source[]): UniqueSource[] {
  const byId = new Map<string, UniqueSource>()
  const withoutId: UniqueSource[] = []
  sources.forEach((src, i) => {
    const docId = (src.doc_id || '').trim()
    const section = (src.section || '').trim()
    if (!docId) {
      withoutId.push({
        docId: `__none_${i}`,
        filename: src.filename,
        source_url: src.source_url,
        source_type: src.source_type,
        source: src.source,
        sections: section ? [section] : [],
        downloadable: false,
      })
      return
    }
    const existing = byId.get(docId)
    if (existing) {
      if (section && !existing.sections.includes(section)) existing.sections.push(section)
      return
    }
    byId.set(docId, {
      docId,
      filename: src.filename,
      source_url: src.source_url,
      source_type: src.source_type,
      source: src.source,
      sections: section ? [section] : [],
      downloadable: true,
    })
  })
  return [...byId.values(), ...withoutId]
}

export function downloadableDocIds(rows: UniqueSource[]): string[] {
  return rows.filter(r => r.downloadable).map(r => r.docId)
}
