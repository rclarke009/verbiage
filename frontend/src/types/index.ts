/** Types aligned with Verbiage FastAPI (app/models.py) and SSE source payloads */

export interface Source {
  filename: string
  source_url?: string
  source_type?: string
  source?: string
  page?: number
  section?: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  chunks_used?: number
}

export interface RetrievedChunk {
  chunk_id: string
  doc_id: string
  score: number
  content_snippet: string
  document_title: string | null
  source: string | null
  source_url?: string | null
}

export interface AskResponseJson {
  answer: string
  top_chunks: RetrievedChunk[]
  prompt_tokens_estimate?: number | null
}

export interface DocumentSummary {
  doc_id: string
  title?: string | null
  source?: string | null
  source_url?: string | null
  source_filename?: string | null
  embedding_model?: string | null
  chunking_config?: Record<string, unknown> | null
  created_at: number
  source_modified_at?: number | null
  num_chunks: number
  snippet?: string | null
}

export interface DocumentsListResponse {
  documents: DocumentSummary[]
}

export interface DriveFileMeta {
  id: string
  name?: string | null
  mimeType?: string | null
  modifiedTime?: string | null
  index_status?: 'not_indexed' | 'indexed' | 'stale'
  num_chunks?: number | null
}

export interface DriveFileListSummary {
  total: number
  indexed: number
  not_indexed: number
  stale: number
}

export interface DriveFileListResponse {
  files: DriveFileMeta[]
  summary: DriveFileListSummary
}

export interface IngestResponse {
  doc_id: string
  num_chunks: number
  embedding_model: string
  dim: number
  embedding_chars_total: number
  embedding_tokens_estimate: number
}

export interface IngestGoogleDriveResponse {
  ingested: number
  skipped: number
  errors: string[]
  doc_ids: string[]
}
