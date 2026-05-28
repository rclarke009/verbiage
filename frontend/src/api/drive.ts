import { apiFetch, readErrorDetail } from '../lib/api'

import type {
  DriveFileListResponse,
  DriveFolderContext,
  IngestBatchEnqueueResponse,
  IngestBatchStatusResponse,
} from '../types'

export async function driveTest(): Promise<{ ok: boolean }> {
  const res = await apiFetch('/drive/test')
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<{ ok: boolean }>
}

export async function driveGetFolder(folderId?: string | null): Promise<DriveFolderContext> {
  const q =
    folderId != null && folderId.trim()
      ? `?folder_id=${encodeURIComponent(folderId.trim())}`
      : ''
  const res = await apiFetch(`/drive/folder${q}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<DriveFolderContext>
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
}): Promise<IngestBatchEnqueueResponse> {
  const res = await apiFetch('/ingest/google-drive', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<IngestBatchEnqueueResponse>
}

export async function getIngestBatchStatus(batchId: string): Promise<IngestBatchStatusResponse> {
  const res = await apiFetch(`/ingest/batches/${encodeURIComponent(batchId)}`)
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<IngestBatchStatusResponse>
}

export function pollIngestBatch(
  batchId: string,
  onUpdate: (status: IngestBatchStatusResponse) => void,
  intervalMs = 2500,
): { stop: () => void; promise: Promise<IngestBatchStatusResponse> } {
  let stopped = false
  let timer: ReturnType<typeof setInterval> | null = null

  const promise = new Promise<IngestBatchStatusResponse>((resolve, reject) => {
    const tick = async () => {
      if (stopped) return
      try {
        const status = await getIngestBatchStatus(batchId)
        onUpdate(status)
        if (status.status === 'completed' || status.status === 'failed') {
          stopped = true
          if (timer) clearInterval(timer)
          resolve(status)
        }
      } catch (e) {
        stopped = true
        if (timer) clearInterval(timer)
        reject(e)
      }
    }
    void tick()
    timer = setInterval(() => void tick(), intervalMs)
  })

  return {
    stop: () => {
      stopped = true
      if (timer) clearInterval(timer)
    },
    promise,
  }
}
