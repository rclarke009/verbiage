import { apiFetch, readErrorDetail } from '../lib/api'

import type {
  DocumentsListResponse,
  IngestResponse,
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
