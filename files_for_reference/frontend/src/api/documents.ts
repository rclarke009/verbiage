import type { DocumentListResponse, StatsResponse, IngestResponse } from '../types'

export async function fetchDocuments(search?: string): Promise<DocumentListResponse> {
  const params = search ? `?search=${encodeURIComponent(search)}` : ''
  const res = await fetch(`/api/documents${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch('/api/documents/stats')
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deleteDocument(fileId: string): Promise<void> {
  const res = await fetch(`/api/documents/${encodeURIComponent(fileId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
}

export async function uploadDocument(file: File): Promise<IngestResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/ingest', { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
