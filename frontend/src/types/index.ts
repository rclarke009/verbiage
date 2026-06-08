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

/** One self-contained lookup: a query and the passages it returned. Not a chat turn. */
export interface LookupResult {
  id: string
  query: string
  answer: string
  sources: Source[]
  chunksUsed: number
  streaming: boolean
}

/** A passage the user kept aside to reuse while drafting a new report. */
export interface SavedPassage {
  id: string
  text: string
  query: string
  sources: Source[]
  savedAt: number
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

export interface DriveFolderContext {
  id: string
  name?: string | null
  path?: string | null
  is_default: boolean
  display_path: string
}

export interface DriveFileListResponse {
  files: DriveFileMeta[]
  summary: DriveFileListSummary
  folder?: DriveFolderContext | null
}

export interface IngestResponse {
  doc_id: string
  num_chunks: number
  embedding_model: string
  dim: number
  embedding_chars_total: number
  embedding_tokens_estimate: number
}

export interface IngestBatchEnqueueResponse {
  batch_id: string
  total: number
  job_ids: string[]
}

export type IngestBatchStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface IngestBatchStatusResponse {
  batch_id: string
  kind: string
  status: IngestBatchStatus
  total: number
  pending: number
  running: number
  succeeded: number
  failed: number
  skipped: number
  errors: string[]
  created_at?: string | null
  updated_at?: string | null
}

/** @deprecated Sync ingest response; Drive ingest now returns IngestBatchEnqueueResponse (202). */
export interface IngestGoogleDriveResponse {
  ingested: number
  skipped: number
  errors: string[]
  doc_ids: string[]
}

export interface ReportWriterSource {
  chunk_id?: string
  doc_id?: string
  score?: number
  snippet?: string
  document_title?: string | null
  source_url?: string | null
}

export interface SectionContent {
  section_key: string
  content: string
  revision_id?: string | null
  origin?: string | null
  sources?: ReportWriterSource[]
}

export interface ClaimPropertyMetadata {
  address?: string
  property_type?: string
  storm_id?: string
  storm_name?: string
  storm_date?: string
  storm_type?: string
  storm_category?: string
  landfall_region?: string
  [key: string]: string | undefined
}

export interface Claim {
  claim_id: string
  user_id: string
  title: string
  property_metadata: Record<string, string>
  field_notes: string
  status: string
  created_at?: string | null
  updated_at?: string | null
  sections?: Record<string, SectionContent>
}

export interface ClaimCreatePayload {
  title?: string
  property_metadata?: Record<string, string>
  field_notes?: string
}

export interface ClaimUpdatePayload {
  title?: string
  property_metadata?: Record<string, string>
  field_notes?: string
}

export interface GenerationRun {
  run_id: string
  claim_id: string
  status: string
  thread_id: string
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
  sections?: Record<string, SectionContent>
}

export interface ReportWriterImage {
  image_id: string
  claim_id: string
  filename: string
  content_type: string
  size_bytes: number
  storage_path: string
  vision_analysis?: Record<string, unknown> | null
  sort_order?: number
}

export interface GenerationSectionState {
  content: string
  streaming: boolean
  sources: ReportWriterSource[]
}

export interface GenerationState {
  runId: string | null
  claimId: string | null
  activeNode: string | null
  status: 'idle' | 'running' | 'complete' | 'refused' | 'error'
  refusalReason: string | null
  retrievedSources: ReportWriterSource[]
  sections: Record<string, GenerationSectionState>
  error: string | null
}
