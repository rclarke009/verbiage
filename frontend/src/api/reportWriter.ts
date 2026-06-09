import { apiFetch, apiOrigin, getAuthFetchInit, readErrorDetail } from '../lib/api'
import type {
  Claim,
  ClaimCreatePayload,
  ClaimUpdatePayload,
  GenerationRun,
  ReportTypeDefinition,
  ReportWriterImage,
  SectionContent,
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
  const res = await apiFetch(`${BASE}/claims/${claimId}/images`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const data = (await res.json()) as { images: ReportWriterImage[] }
  return data.images
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

export async function syncClaimPhotosFromDrive(claimId: string, folderId?: string) {
  const res = await apiFetch(`${BASE}/claims/${claimId}/photos/sync-drive`, {
    method: 'POST',
    body: JSON.stringify(folderId ? { folder_id: folderId } : {}),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{
    batch_id: string | null
    total: number
    image_count: number
    job_ids: string[]
  }>
}

export async function getClaimPhotoBatchStatus(claimId: string, batchId: string) {
  const res = await apiFetch(`${BASE}/claims/${claimId}/photos/batch/${batchId}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<import('../types').IngestBatchStatusResponse>
}

export async function getPhotoAnalysisCounts(claimId: string) {
  const res = await apiFetch(`${BASE}/claims/${claimId}/photos/analysis-counts`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<import('../types').PhotoAnalysisCounts>
}

export function generateStreamUrl(claimId: string): string {
  return `${apiOrigin()}/report-writer/claims/${claimId}/generate`
}

export function regenerateSectionStreamUrl(claimId: string, sectionKey: string): string {
  return `${apiOrigin()}/report-writer/claims/${claimId}/sections/${sectionKey}/regenerate`
}

export async function exportClaimDocx(claimId: string, title: string): Promise<void> {
  const init = await getAuthFetchInit()
  const res = await fetch(`${apiOrigin()}/report-writer/claims/${claimId}/export/docx`, init)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(title || 'report').replace(/\s+/g, '_').slice(0, 80)}.docx`
  a.click()
  URL.revokeObjectURL(url)
}

export async function fetchClaimPdfBlob(claimId: string): Promise<Blob> {
  const init = await getAuthFetchInit()
  const res = await fetch(`${apiOrigin()}/report-writer/claims/${claimId}/export/pdf`, init)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.blob()
}

export { getAuthFetchInit }
