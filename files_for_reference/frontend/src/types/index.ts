export interface Source {
  filename: string
  source_url: string
  source_type: string
  page: number
  section: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  chunks_used?: number
}

export interface DocumentItem {
  file_id: string
  filename: string
  source_type: string
  pages: number
  chunks: number
  ocr_used: boolean
  ingested_at: string
  source_url: string
}

export interface DocumentListResponse {
  documents: DocumentItem[]
  total: number
  total_chunks: number
}

export interface StatsResponse {
  total_reports: number
  total_chunks: number
  avg_chunks_per_doc: number
}

export interface IngestResponse {
  file_id: string
  filename: string
  chunks: number
  pages: number
  ocr_used: boolean
  skipped: boolean
}

export interface DriveStatusResponse {
  configured: boolean
  credentials_ok: boolean
  connected: boolean
  service_email: string
  file_count: number
  error: string
}

export interface DriveSyncResponse {
  ingested: number
  skipped: number
  errors: string[]
}

export interface VisionResponse {
  classification: string
  confidence: string
  findings: string[]
  recommendation: string
  notes: string
  raw: string
}

export interface RagGroundedVisionResponse {
  vision_result: VisionResponse
  rag_answer: string
  sources: Source[]
  chunks_used: number
  retrieval_query: string
  skipped: boolean
  skip_reason: string
}
