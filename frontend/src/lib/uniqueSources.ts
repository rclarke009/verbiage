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

const DRIVE_FILE_IN_URL = /\/(?:file|document)\/d\/([a-zA-Z0-9_-]+)/
const DRIVE_ID_OR_CHUNK = /^([a-zA-Z0-9_-]{20,})(?::\d+)?$/

/** Drive file id from SSE doc_id, an open-in-Drive URL, or a chunk_id used as section. */
export function resolveSourceDocId(src: Source): string | null {
  const explicit = (src.doc_id || '').trim()
  if (explicit) return explicit
  const fromUrl = DRIVE_FILE_IN_URL.exec(src.source_url || '')
  if (fromUrl?.[1]) return fromUrl[1]
  const section = (src.section || '').trim()
  const fromSection = DRIVE_ID_OR_CHUNK.exec(section)
  if (fromSection?.[1]) return fromSection[1]
  return null
}

function displaySection(section: string | undefined, resolvedId: string | null): string {
  const raw = (section || '').trim()
  if (!raw) return ''
  if (resolvedId && (raw === resolvedId || raw.startsWith(`${resolvedId}:`))) return ''
  return raw
}

/** Collapse citation rows into one entry per document, preserving section labels. */
export function uniqueSourcesByDoc(sources: Source[]): UniqueSource[] {
  const byId = new Map<string, UniqueSource>()
  const withoutId: UniqueSource[] = []
  sources.forEach((src, i) => {
    const resolved = resolveSourceDocId(src)
    const section = displaySection(src.section, resolved)
    if (!resolved) {
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
    const existing = byId.get(resolved)
    if (existing) {
      if (section && !existing.sections.includes(section)) existing.sections.push(section)
      return
    }
    byId.set(resolved, {
      docId: resolved,
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
