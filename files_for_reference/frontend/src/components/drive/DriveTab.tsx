import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchDriveStatus, syncDrive } from '../../api/drive'
import type { DriveSyncResponse } from '../../types'

function StatusCard({ label, ok, detail }: { label: string; ok: boolean; detail?: string }) {
  return (
    <div style={{
      flex: 1, border: `1px solid ${ok ? '#a5d6a7' : '#ef9a9a'}`,
      borderRadius: 8, padding: '12px 16px', background: ok ? '#E8F5E9' : '#FFEBEE',
    }}>
      <div style={{ fontWeight: 600, fontSize: 13 }}>
        {ok ? '✓' : '✗'} {label}
      </div>
      {detail && <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>{detail}</div>}
    </div>
  )
}

export function DriveTab() {
  const [syncResult, setSyncResult] = useState<DriveSyncResponse | null>(null)
  const [syncError, setSyncError] = useState('')

  const { data: status, isLoading } = useQuery({
    queryKey: ['driveStatus'],
    queryFn: fetchDriveStatus,
  })

  const syncMutation = useMutation({
    mutationFn: (source: 'drive' | 'both') => syncDrive(source),
    onSuccess: (data) => { setSyncResult(data); setSyncError('') },
    onError: (e) => setSyncError(e instanceof Error ? e.message : 'Sync failed'),
  })

  return (
    <div>
      <h2 style={{ marginTop: 0, color: '#1976D2', fontSize: 18 }}>☁️ Google Drive</h2>

      {isLoading && <p style={{ color: '#888', fontSize: 13 }}>Checking Drive status…</p>}

      {status && (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <StatusCard label="Configured" ok={status.configured} />
            <StatusCard label="Credentials Valid" ok={status.credentials_ok} detail={status.service_email || undefined} />
            <StatusCard label="Drive Connected" ok={status.connected} detail={status.connected ? `${status.file_count} files found` : undefined} />
          </div>

          {status.error && (
            <div style={{ background: '#FFEBEE', borderRadius: 6, padding: '10px 14px', color: '#c62828', fontSize: 13, marginBottom: 16 }}>
              {status.error}
            </div>
          )}

          {status.connected && (
            <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
              <button
                onClick={() => syncMutation.mutate('drive')}
                disabled={syncMutation.isPending}
                style={{
                  background: '#1976D2', color: '#fff', border: 'none', borderRadius: 6,
                  padding: '9px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  opacity: syncMutation.isPending ? 0.6 : 1,
                }}
              >
                {syncMutation.isPending ? 'Syncing…' : '☁️ Sync from Drive'}
              </button>
              <button
                onClick={() => syncMutation.mutate('both')}
                disabled={syncMutation.isPending}
                style={{
                  background: '#fff', color: '#1976D2', border: '1px solid #1976D2',
                  borderRadius: 6, padding: '9px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  opacity: syncMutation.isPending ? 0.6 : 1,
                }}
              >
                Sync Drive + Local
              </button>
            </div>
          )}

          {syncResult && (
            <div style={{ background: '#E8F5E9', borderRadius: 6, padding: '10px 14px', fontSize: 13, color: '#2e7d32', marginBottom: 12 }}>
              ✓ Sync complete — {syncResult.ingested} ingested, {syncResult.skipped} skipped
              {syncResult.errors.length > 0 && (
                <ul style={{ marginTop: 6, color: '#c62828' }}>
                  {syncResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              )}
            </div>
          )}
          {syncError && (
            <div style={{ background: '#FFEBEE', borderRadius: 6, padding: '10px 14px', color: '#c62828', fontSize: 13 }}>
              ✗ {syncError}
            </div>
          )}

          {!status.configured && (
            <details style={{ marginTop: 20 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: 14, color: '#1976D2' }}>
                Setup instructions
              </summary>
              <ol style={{ fontSize: 13, lineHeight: 1.8, marginTop: 8, color: '#333' }}>
                <li>Create a Google Cloud project and enable the Drive API</li>
                <li>Create a service account and download the JSON key</li>
                <li>Set <code>GOOGLE_CREDENTIALS_PATH</code> to the JSON file path in your <code>.env</code></li>
                <li>Set <code>GOOGLE_DRIVE_FOLDER_ID</code> to your Drive folder ID</li>
                <li>Share the Drive folder with the service account email</li>
                <li>Restart the API server</li>
              </ol>
            </details>
          )}
        </>
      )}
    </div>
  )
}
