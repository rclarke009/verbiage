import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { driveListFiles, driveTest, ingestGoogleDrive } from '../../api/drive'
import { apiOrigin } from '../../lib/api'
import type { DriveFileMeta, IngestGoogleDriveResponse } from '../../types'

import type { CSSProperties } from 'react'

export function DriveTab() {
  const [folderId, setFolderId] = useState('')
  const [files, setFiles] = useState<DriveFileMeta[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const base = apiOrigin()

  const testMutation = useMutation({
    mutationFn: () => driveTest(),
    onSuccess: () => {
      setErr('')
      setMsg('Drive credentials OK (server-side token).')
    },
    onError: (e: Error) => {
      setMsg('')
      setErr(e.message)
    },
  })

  const listMutation = useMutation({
    mutationFn: () => driveListFiles(folderId || undefined),
    onSuccess: data => {
      setFiles(data.files ?? [])
      setSelected(new Set())
      setErr('')
      setMsg(`Found ${data.files?.length ?? 0} Google Doc(s).`)
    },
    onError: (e: Error) => {
      setFiles([])
      setMsg('')
      setErr(e.message)
    },
  })

  const ingestMutation = useMutation({
    mutationFn: () =>
      ingestGoogleDrive({
        folder_id: folderId.trim() || null,
        file_ids: selected.size ? Array.from(selected) : null,
      }),
    onSuccess: (r: IngestGoogleDriveResponse) => {
      setErr('')
      setMsg(
        `Ingest finished: ${r.ingested} new, ${r.skipped} skipped.` +
          (r.errors.length ? ` (${r.errors.length} error rows — check server logs).` : ''),
      )
    },
    onError: (e: Error) => {
      setMsg('')
      setErr(e.message)
    },
  })

  const canIngestQuick = !!(folderId.trim() || selected.size)

  const toggle = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div>
      <h2 style={{ marginTop: 0, color: '#0969da', fontSize: 18 }}>Google Drive</h2>

      <p style={{ fontSize: 13, color: '#57606a', lineHeight: 1.6 }}>
        The API reads Drive using server credentials (<code>GOOGLE_REFRESH_TOKEN</code> and client
        id/secret). To obtain a refresh token, open{' '}
        <a href={`${base}/auth/google`} target="_blank" rel="noopener noreferrer">
          /auth/google
        </a>{' '}
        in your browser while the API origin matches <code>GOOGLE_REDIRECT_URI</code>; copy the shown
        value into your environment.
      </p>

      <div style={{ marginBottom: 14 }}>
        <button
          type="button"
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
          style={btnSecondary}
        >
          {testMutation.isPending ? 'Testing…' : 'Test credentials'}
        </button>
      </div>

      <label style={{ fontSize: 13, color: '#24292f', display: 'block', marginBottom: 8 }}>
        Optional folder ID (narrows listing and ingest folder mode)
        <input
          value={folderId}
          onChange={e => setFolderId(e.target.value)}
          placeholder="Google Drive folder id"
          style={inputStyle}
        />
      </label>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        <button type="button" onClick={() => listMutation.mutate()} disabled={listMutation.isPending} style={btnPrimary}>
          {listMutation.isPending ? 'Listing…' : 'List Docs'}
        </button>
        <button
          type="button"
          onClick={() => {
            if (!canIngestQuick) {
              if (!window.confirm('No folder ID and nothing selected — the server default scope applies. Continue?'))
                return
            }
            ingestMutation.mutate()
          }}
          disabled={ingestMutation.isPending}
          style={btnPrimary}
        >
          {ingestMutation.isPending ? 'Ingesting…' : 'Ingest'}
        </button>
      </div>

      {!canIngestQuick && (
        <p style={{ fontSize: 12, color: '#57606a', marginBottom: 12 }}>
          Select files below or paste a folder id to avoid unintended wide imports.
        </p>
      )}

      {msg && (
        <div style={{ ...banner, background: '#dafbe1', color: '#1a7f37' }}>
          {msg}
        </div>
      )}
      {err && (
        <div style={{ ...banner, background: '#FFEBEE', color: '#cf222e' }}>
          {err}
        </div>
      )}

      {files.length > 0 && (
        <div
          style={{
            marginTop: 12,
            maxHeight: 360,
            overflow: 'auto',
            border: '1px solid #d0d7de',
            borderRadius: 8,
          }}
        >
          {files.map(f => (
            <label
              key={f.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 12px',
                borderBottom: '1px solid #f0f0f0',
                fontSize: 13,
              }}
            >
              <input type="checkbox" checked={selected.has(f.id)} onChange={() => toggle(f.id)} />
              <span style={{ flex: 1 }}>{f.name || f.id}</span>
              <span style={{ color: '#57606a', fontSize: 11 }}>{f.mimeType ?? ''}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

const btnPrimary: CSSProperties = {
  background: '#0969da',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '8px 16px',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
}

const btnSecondary: CSSProperties = {
  ...btnPrimary,
  background: '#f6f8fa',
  color: '#24292f',
  border: '1px solid #d0d7de',
}

const inputStyle: CSSProperties = {
  display: 'block',
  width: '100%',
  marginTop: 6,
  boxSizing: 'border-box',
  padding: '8px 12px',
  borderRadius: 6,
  border: '1px solid #d0d7de',
  fontSize: 13,
}

const banner: CSSProperties = {
  borderRadius: 6,
  padding: '10px 14px',
  fontSize: 13,
  marginBottom: 12,
}
