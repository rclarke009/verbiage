import { apiFetch, apiFetchRetry, apiOrigin, getAuthFetchInit, readErrorDetail } from '../lib/api'
import type {
  Claim,
  ClaimCreatePayload,
  ClaimUpdatePayload,
  GenerationRun,
  ReportTypeDefinition,
  ReportWriterImage,
  SectionContent,
  WeatherOptionsResponse,
  AddressSuggestion,
  HistoricalAerialsResponse,
  PropertyMapResponse,
  PropertyAppraiserResponse,
} from '../types'

const BASE = '/report-writer'

export async function listReportTypes(): Promise<ReportTypeDefinition[]> {
  const res = await apiFetch(`${BASE}/report-types`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const data = (await res.json()) as { report_types: ReportTypeDefinition[] }
  return data.report_types
}

export async function listClaims(): Promise<Claim[]> {
  const res = await apiFetch(`${BASE}/claims`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const data = (await res.json()) as { claims: Claim[] }
  return data.claims
}

export async function createClaim(payload: ClaimCreatePayload): Promise<Claim> {
  const res = await apiFetch(`${BASE}/claims`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<Claim>
}

export async function getClaim(claimId: string): Promise<Claim> {
  const res = await apiFetch(`${BASE}/claims/${claimId}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<Claim>
}

export async function updateClaim(claimId: string, payload: ClaimUpdatePayload): Promise<Claim> {
  const res = await apiFetch(`${BASE}/claims/${claimId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<Claim>
}

export async function deleteClaim(claimId: string): Promise<void> {
  const res = await apiFetch(`${BASE}/claims/${claimId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await readErrorDetail(res))
}

export async function updateSection(
  claimId: string,
  sectionKey: string,
  content: string,
): Promise<SectionContent> {
  const res = await apiFetch(`${BASE}/claims/${claimId}/sections/${sectionKey}`, {
    method: 'PATCH',
    body: JSON.stringify({ content }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<SectionContent>
}

export async function listRuns(claimId: string): Promise<GenerationRun[]> {
  const res = await apiFetch(`${BASE}/claims/${claimId}/runs`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const data = (await res.json()) as { runs: GenerationRun[] }
  return data.runs
}

export async function getRun(claimId: string, runId: string): Promise<GenerationRun> {
  const res = await apiFetch(`${BASE}/claims/${claimId}/runs/${runId}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<GenerationRun>
}

export async function uploadClaimImage(claimId: string, file: File): Promise<ReportWriterImage> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetch(`${BASE}/claims/${claimId}/images`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<ReportWriterImage>
}

export async function listClaimImages(claimId: string): Promise<ReportWriterImage[]> {
  const res = await apiFetchRetry(`${BASE}/claims/${claimId}/images`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const data = (await res.json()) as { images: ReportWriterImage[] }
  return data.images
}

export async function fetchClaimWeather(address: string, date: string): Promise<WeatherOptionsResponse> {
  const q = new URLSearchParams({ address, date })
  const res = await apiFetch(`${BASE}/weather?${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<WeatherOptionsResponse>
}

export async function fetchPropertyMap(address: string, claimId?: string): Promise<PropertyMapResponse> {
  const q = new URLSearchParams({ address })
  if (claimId) q.set('claim_id', claimId)
  const res = await apiFetch(`${BASE}/property-map?${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<PropertyMapResponse>
}

export async function fetchPropertyAppraiser(
  address: string,
  claimId?: string,
  force = false,
): Promise<PropertyAppraiserResponse> {
  const q = new URLSearchParams({ address })
  if (claimId) q.set('claim_id', claimId)
  if (force) q.set('force', 'true')
  const res = await apiFetch(`${BASE}/property-appraiser?${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<PropertyAppraiserResponse>
}

export async function fetchHistoricalAerials(
  address: string,
  date: string,
  claimId?: string,
): Promise<HistoricalAerialsResponse> {
  const q = new URLSearchParams({ address, date })
  if (claimId) q.set('claim_id', claimId)
  const res = await apiFetch(`${BASE}/historical-aerials?${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<HistoricalAerialsResponse>
}

export async function matchDrivePhotoFolder(address: string) {
  const q = new URLSearchParams({ address })
  const res = await apiFetch(`${BASE}/drive/match-folder?${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{
    matches: import('../types').DriveFolderMatch[]
    suggested_id?: string | null
    jobs_root?: { id: string; display_path?: string } | null
  }>
}

export async function suggestAddresses(q: string): Promise<AddressSuggestion[]> {
  const params = new URLSearchParams({ q })
  const res = await apiFetch(`${BASE}/address/suggest?${params}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const data = (await res.json()) as { suggestions: AddressSuggestion[] }
  return data.suggestions
}

export async function syncClaimPhotosFromDrive(claimId: string, folderId?: string) {
  // Omit folder_id so the server syncs every linked folder on the claim.
  // Passing folder_id forces a single-folder override (legacy / one-off use).
  const res = await apiFetchRetry(
    `${BASE}/claims/${claimId}/photos/sync-drive`,
    {
      method: 'POST',
      body: JSON.stringify(folderId ? { folder_id: folderId } : {}),
    },
    { retries: 4, baseDelayMs: 1500 },
  )
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{
    batch_id: string | null
    total: number
    image_count: number
    job_ids: string[]
    folder_ids?: string[]
  }>
}

export async function retryStuckClaimPhotos(claimId: string) {
  const res = await apiFetchRetry(
    `${BASE}/claims/${claimId}/photos/retry-stuck`,
    { method: 'POST', body: '{}' },
    { retries: 4, baseDelayMs: 1500 },
  )
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{
    reset_images: number
    reclaimed_jobs: number
    batch_id: string | null
    enqueued: number
    total: number
    image_count: number
    job_ids: string[]
  }>
}

export async function getClaimPhotoBatchStatus(claimId: string, batchId: string) {
  const res = await apiFetchRetry(`${BASE}/claims/${claimId}/photos/batch/${batchId}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<import('../types').IngestBatchStatusResponse>
}

export async function cancelPhotoBatch(claimId: string, batchId: string) {
  const res = await apiFetch(`${BASE}/claims/${claimId}/photos/batch/${batchId}/cancel`, {
    method: 'POST',
    body: '{}',
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{ status: string; cancelled_jobs: number }>
}

export async function cancelGenerationRun(claimId: string, runId: string) {
  const res = await apiFetch(`${BASE}/claims/${claimId}/generate/cancel`, {
    method: 'POST',
    body: JSON.stringify({ run_id: runId }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{ status: string }>
}

export async function getPhotoAnalysisCounts(claimId: string) {
  const res = await apiFetchRetry(`${BASE}/claims/${claimId}/photos/analysis-counts`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<import('../types').PhotoAnalysisCounts>
}

export function generateStreamUrl(claimId: string): string {
  return `${apiOrigin()}/report-writer/claims/${claimId}/generate`
}

export function regenerateSectionStreamUrl(claimId: string, sectionKey: string): string {
  return `${apiOrigin()}/report-writer/claims/${claimId}/sections/${sectionKey}/regenerate`
}

/** Export endpoints can be slow (Drive photo fetch + render); retry transient gateway blips. */
const EXPORT_FETCH_OPTS = { retries: 4, baseDelayMs: 1500 } as const

export async function importJobPackage(file: File): Promise<Claim> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetch(`${BASE}/claims/import-job-package`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<Claim>
}

export async function exportClaimDocx(claimId: string, title: string, mode: 'pages' | 'full' = 'pages'): Promise<void> {
  const res = await apiFetchRetry(
    `${BASE}/claims/${claimId}/export/docx?mode=${mode}`,
    { method: 'GET' },
    EXPORT_FETCH_OPTS,
  )
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(title || 'report').replace(/\s+/g, '_').slice(0, 80)}.docx`
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadClaimPdf(claimId: string, title: string, mode: 'full' | 'chapter' = 'chapter'): Promise<void> {
  const blob = await fetchClaimPdfBlob(claimId, undefined, mode)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(title || 'report').replace(/\s+/g, '_').slice(0, 80)}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

export async function fetchClaimPdfBlob(
  claimId: string,
  signal?: AbortSignal,
  mode: 'full' | 'chapter' = 'full',
): Promise<Blob> {
  const init = await getAuthFetchInit({ method: 'GET', signal })
  const res = await apiFetchRetry(
    `${BASE}/claims/${claimId}/export/pdf?mode=${mode}`,
    init,
    EXPORT_FETCH_OPTS,
  )
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const blob = await res.blob()
  if (!(await blob.slice(0, 5).text()).startsWith('%PDF')) {
    throw new Error('Export did not return a valid PDF (server may be overloaded — try again)')
  }
  return blob
}

export { getAuthFetchInit }
