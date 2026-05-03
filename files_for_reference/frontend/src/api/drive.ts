import type { DriveStatusResponse, DriveSyncResponse } from '../types'

export async function fetchDriveStatus(): Promise<DriveStatusResponse> {
  const res = await fetch('/api/drive/status')
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function syncDrive(source: 'drive' | 'both', localPath?: string): Promise<DriveSyncResponse> {
  const res = await fetch('/api/drive/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, local_path: localPath ?? null }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
