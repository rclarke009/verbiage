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

export interface SimilarTitleMatch {
  doc_id: string
  title?: string | null
  score: number
}

export interface SimilarTitlesResponse {
  matches: SimilarTitleMatch[]
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

export type IngestBatchStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

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
  cancelled?: number
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
  report_type?: string
  address?: string
  address2?: string
  city?: string
  state?: string
  zip?: string
  property_type?: string
  storm_id?: string
  storm_name?: string
  storm_date?: string
  storm_date_iso?: string
  storm_type?: string
  storm_category?: string
  landfall_region?: string
  wind_speed_mph?: string
  wind_gust_mph?: string
  hail_size_in?: string
  weather_stations?: string
  weather_resolved_address?: string
  weather_date_iso?: string
  weather_source?: string
  weather_fetched_at?: string
  weather_fetch_key?: string
  weather_wind_speed_source?: string
  weather_wind_gust_source?: string
  weather_hail_source?: string
  weather_custom_wind_speed?: string
  weather_custom_wind_gust?: string
  weather_custom_hail?: string
  weather_candidates_json?: string
  property_map_fetch_key?: string
  property_map_resolved_address?: string
  property_latitude?: string
  property_longitude?: string
  property_map_satellite_path?: string
  property_map_roadmap_path?: string
  property_map_fetched_at?: string
  [key: string]: string | undefined
}

export type WeatherMetric = 'wind_speed' | 'wind_gust' | 'hail_size' | 'precip'

export interface WeatherCandidate {
  id: string
  metric: WeatherMetric
  value: number
  unit: string
  source: string
  label: string
  station?: string | null
  distance_mi?: number | null
  tier: number
  recommended?: boolean
  recommendation_reason?: string | null
}

export interface WeatherOptionsResponse {
  wind_speed_mph: number | null
  wind_gust_mph: number | null
  hail_size_in: number | null
  precip_in?: number | null
  stations: string[]
  resolved_address: string
  latitude: number | null
  longitude: number | null
  date_iso: string
  date_display: string
  source: string
  fetch_key: string
  candidates: WeatherCandidate[]
  selected: Record<string, string>
  attribution: string[]
}

/** @deprecated Use WeatherOptionsResponse */
export type WeatherSnapshot = WeatherOptionsResponse

export interface PropertyMapResponse {
  resolved_address: string
  latitude: number | null
  longitude: number | null
  fetch_key: string
  satellite_url?: string | null
  roadmap_url?: string | null
  property_map_satellite_path?: string | null
  property_map_roadmap_path?: string | null
  satellite_preview: string
  roadmap_preview: string
  attribution: string[]
}

export interface ReportTypeSection {
  key: string
  label: string
}

export interface ReportTypeDefinition {
  id: string
  label: string
  description: string
  sections: ReportTypeSection[]
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
  storage_path?: string | null
  drive_file_id?: string | null
  source_url?: string | null
  vision_analysis?: Record<string, unknown> | null
  analysis_status?: string | null
  sort_order?: number
  /** Present after upload when a background vision job was enqueued */
  batch_id?: string | null
  enqueued?: number
  job_ids?: string[]
}

export interface DriveFolderMatch {
  id: string
  name: string
  score: number
  source_url: string
}

export interface AddressSuggestion {
  id: string
  label: string
  address: string
  address2?: string
  city?: string
  state?: string
  zip?: string
}

export interface PhotoAnalysisCounts {
  total: number
  pending: number
  running: number
  succeeded: number
  failed: number
  with_damage?: number
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
  status: 'idle' | 'running' | 'complete' | 'refused' | 'error' | 'cancelled'
  refusalReason: string | null
  retrievedSources: ReportWriterSource[]
  sections: Record<string, GenerationSectionState>
  error: string | null
}
