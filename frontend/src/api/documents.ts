import { apiFetch, readErrorDetail } from '../lib/api'

import type {
  DocumentsListResponse,
  IngestResponse,
  SimilarTitlesResponse,
} from '../types'

export async function listDocuments(): Promise<DocumentsListResponse> {
  const res = await apiFetch('/documents')
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<DocumentsListResponse>
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await apiFetch(`/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await readErrorDetail(res))
}

export async function fetchSimilarTitles(
  proposed: string,
  options?: { limit?: number; minRatio?: number },
): Promise<SimilarTitlesResponse> {
  const params = new URLSearchParams({ proposed })
  if (options?.limit != null) params.set('limit', String(options.limit))
  if (options?.minRatio != null) params.set('min_ratio', String(options.minRatio))
  const res = await apiFetch(`/documents/similar-titles?${params}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<SimilarTitlesResponse>
}

export async function uploadDocumentPdf(file: File): Promise<IngestResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetch('/ingest/file', { method: 'POST', body: form })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<IngestResponse>
}

export function summarizeDocuments(rows: DocumentsListResponse['documents']) {
  let totalChunks = 0
  for (const d of rows) totalChunks += d.num_chunks
  const n = rows.length
  return {
    total_reports: n,
    total_chunks: totalChunks,
    avg_chunks_per_doc: n === 0 ? 0 : Math.round((totalChunks / n) * 10) / 10,
  }
}

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1])
    } catch {
      return fallback
    }
  }
  const quoted = /filename="([^"]+)"/i.exec(header)
  if (quoted?.[1]) return quoted[1]
  const plain = /filename=([^;]+)/i.exec(header)
  if (plain?.[1]) return plain[1].trim()
  return fallback
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadDocumentFile(docId: string, fallbackName: string): Promise<void> {
  const res = await apiFetch(`/documents/${encodeURIComponent(docId)}/file`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const blob = await res.blob()
  const name = filenameFromDisposition(res.headers.get('Content-Disposition'), fallbackName)
  triggerBlobDownload(blob, name)
}

export async function downloadDocumentsZip(docIds: string[]): Promise<void> {
  const res = await apiFetch('/documents/download-zip', {
    method: 'POST',
    body: JSON.stringify({ doc_ids: docIds }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const blob = await res.blob()
  const name = filenameFromDisposition(res.headers.get('Content-Disposition'), 'sources.zip')
  triggerBlobDownload(blob, name)
}

export async function downloadCitedSources(
  items: { docId: string; filename: string }[],
): Promise<void> {
  if (items.length === 1) {
    await downloadDocumentFile(items[0].docId, items[0].filename || 'document')
    return
  }
  await downloadDocumentsZip(items.map(i => i.docId))
}

