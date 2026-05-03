import { apiFetch, readErrorDetail } from '../lib/api'

import type { DriveFileListResponse, IngestGoogleDriveResponse } from '../types'

export async function driveTest(): Promise<{ ok: boolean }> {
  const res = await apiFetch('/drive/test')
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{ ok: boolean }>
}

export async function driveListFiles(folderId?: string | null): Promise<DriveFileListResponse> {
  const q =
    folderId != null && folderId.trim()
      ? `?folder_id=${encodeURIComponent(folderId.trim())}`
      : ''
  const res = await apiFetch(`/drive/files${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<DriveFileListResponse>
}

export async function ingestGoogleDrive(body: {
  folder_id?: string | null
  file_ids?: string[] | null
}): Promise<IngestGoogleDriveResponse> {
  const res = await apiFetch('/ingest/google-drive', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<IngestGoogleDriveResponse>
}
