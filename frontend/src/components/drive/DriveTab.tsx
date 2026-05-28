import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { driveListFiles, driveTest, ingestGoogleDrive, pollIngestBatch } from '../../api/drive'
import { useAuth } from '../../context/AuthContext'
import { apiOrigin } from '../../lib/api'
import {
  DRIVE_FOLDER_STORAGE_KEY,
  driveFolderUrl,
  parseDriveFolderInput,
  resolveDriveFolderForApi,
} from '../../lib/driveFolder'
import type { DriveFileListSummary, DriveFileMeta, IngestBatchStatusResponse } from '../../types'

import type { CSSProperties } from 'react'

function driveFileTypeLabel(mimeType?: string | null): string {
  if (!mimeType) return ''
  if (mimeType === 'application/vnd.google-apps.document') return 'GDoc'
  if (mimeType === 'application/pdf') return 'PDF'
  if (mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    return 'DOCX'
  return ''
}

function formatListSummary(summary: DriveFileListSummary): string {
  return (
    `Found ${summary.total} ingestable file(s) — ` +
    `${summary.indexed} indexed, ${summary.not_indexed} not indexed, ${summary.stale} stale.`
  )
}

function defaultSelection(files: DriveFileMeta[]): Set<string> {
  return new Set(files.filter(f => f.index_status !== 'indexed').map(f => f.id))
}

function IndexStatusBadge({ file }: { file: DriveFileMeta }) {
  const status = file.index_status ?? 'not_indexed'
  const styles: Record<string, CSSProperties> = {
    not_indexed: { background: '#f6f8fa', color: '#57606a', border: '1px solid #d0d7de' },
    indexed: { background: '#dafbe1', color: '#1a7f37', border: '1px solid #aceebb' },
    stale: { background: '#fff8c5', color: '#9a6700', border: '1px solid #fae17d' },
  }
  const labels: Record<string, string> = {
    not_indexed: 'Not indexed',
    indexed: 'Indexed',
    stale: 'Stale',
  }
  const title =
    status === 'stale'
      ? 'Drive doc changed since last ingest'
      : status === 'indexed' && file.num_chunks != null
        ? `${file.num_chunks} chunks in index`
        : undefined

  return (
    <span
      title={title}
      style={{
        ...styles[status],
        fontSize: 11,
        fontWeight: 600,
        borderRadius: 4,
        padding: '2px 8px',
        whiteSpace: 'nowrap',
      }}
    >
      {labels[status]}
      {status === 'indexed' && file.num_chunks != null ? ` · ${file.num_chunks}` : ''}
    </span>
  )
}

export function DriveTab() {
  const { publicConfig } = useAuth()
  const teamInboxId = publicConfig?.google_drive_default_folder_id ?? ''
  const [folderInput, setFolderInput] = useState('')
  const [folderParseError, setFolderParseError] = useState('')
  const [files, setFiles] = useState<DriveFileMeta[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const base = apiOrigin()
  const queryClient = useQueryClient()
  const initDoneRef = useRef(false)
  const autoListedRef = useRef(false)

  const apiFolderId = () => resolveDriveFolderForApi(folderInput, teamInboxId)
  const effectiveFolderId = apiFolderId()

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
    mutationFn: () => driveListFiles(apiFolderId()),
    onSuccess: data => {
      const fileList = data.files ?? []
      setFiles(fileList)
      setSelected(defaultSelection(fileList))
      setErr('')
      setMsg(data.summary ? formatListSummary(data.summary) : `Found ${fileList.length} ingestable file(s).`)
    },
    onError: (e: Error) => {
      setFiles([])
      setSelected(new Set())
      setMsg('')
      setErr(e.message)
    },
  })

  const [batchStatus, setBatchStatus] = useState<IngestBatchStatusResponse | null>(null)

  const formatBatchProgress = (s: IngestBatchStatusResponse) =>
    `Ingesting ${s.total} doc(s): ${s.succeeded} done, ${s.pending + s.running} in progress` +
    (s.failed ? `, ${s.failed} failed` : '') +
    (s.skipped ? `, ${s.skipped} skipped` : '')

  const ingestMutation = useMutation({
    mutationFn: async () => {
      const enqueued = await ingestGoogleDrive({
        folder_id: apiFolderId() ?? null,
        file_ids: selected.size ? Array.from(selected) : null,
      })
      setBatchStatus(null)
      setErr('')
      setMsg(`Queued ${enqueued.total} document(s)…`)
      const { promise } = pollIngestBatch(enqueued.batch_id, status => {
        setBatchStatus(status)
        setMsg(formatBatchProgress(status))
      })
      return promise
    },
    onSuccess: finalStatus => {
      setErr('')
      const ingestMsg =
        `Ingest finished: ${finalStatus.succeeded} indexed, ${finalStatus.skipped} skipped.` +
        (finalStatus.failed
          ? ` ${finalStatus.failed} failed` +
            (finalStatus.errors.length ? ` — ${finalStatus.errors.slice(0, 2).join('; ')}` : '')
          : '')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      listMutation.mutate(undefined, {
        onSuccess: data => {
          setMsg(
            data.summary
              ? `${ingestMsg} ${formatListSummary(data.summary)}`
              : `${ingestMsg} Found ${data.files?.length ?? 0} ingestable file(s).`,
          )
        },
        onError: () => {
          setMsg(ingestMsg)
        },
      })
      setBatchStatus(null)
    },
    onError: (e: Error) => {
      setBatchStatus(null)
      setMsg('')
      setErr(e.message)
    },
  })

  useEffect(() => {
    if (!publicConfig || initDoneRef.current) return
    initDoneRef.current = true
    const stored = localStorage.getItem(DRIVE_FOLDER_STORAGE_KEY)
    setFolderInput(stored || teamInboxId || '')
  }, [publicConfig, teamInboxId])

  useEffect(() => {
    if (!initDoneRef.current || autoListedRef.current || !publicConfig) return
    const id = resolveDriveFolderForApi(folderInput, teamInboxId)
    if (!id) return
    autoListedRef.current = true
    listMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once when folder resolves after init
  }, [folderInput, publicConfig, teamInboxId])

  const commitFolderInput = () => {
    const { id, error } = parseDriveFolderInput(folderInput)
    if (error) {
      setFolderParseError(error)
      return
    }
    setFolderParseError('')
    if (id) {
      setFolderInput(id)
      if (teamInboxId && id === teamInboxId) {
        localStorage.removeItem(DRIVE_FOLDER_STORAGE_KEY)
      } else if (id) {
        localStorage.setItem(DRIVE_FOLDER_STORAGE_KEY, id)
      }
    } else if (!folderInput.trim()) {
      localStorage.removeItem(DRIVE_FOLDER_STORAGE_KEY)
    }
  }

  const resetToTeamInbox = () => {
    localStorage.removeItem(DRIVE_FOLDER_STORAGE_KEY)
    setFolderInput(teamInboxId)
    setFolderParseError('')
    listMutation.mutate()
  }

  const canIngestQuick = !!(effectiveFolderId || selected.size)
  const showResetInbox =
    !!teamInboxId && folderInput.trim() !== '' && folderInput.trim() !== teamInboxId

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
        value into your environment. Supported file types: Google Docs, PDF, and Word (.docx). Max
        download size 50 MB per file.
        {teamInboxId ? (
          <>
            {' '}
            The team ingest inbox is pre-configured; paste another folder link only when ingesting
            elsewhere.
          </>
        ) : null}
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
        Inbox folder (paste link or ID)
        <input
          value={folderInput}
          onChange={e => {
            setFolderInput(e.target.value)
            setFolderParseError('')
          }}
          onBlur={commitFolderInput}
          placeholder={
            teamInboxId
              ? 'Team inbox (default) — paste another folder to override'
              : 'Paste drive.google.com/.../folders/… or folder id'
          }
          style={inputStyle}
        />
      </label>

      {folderParseError && (
        <p style={{ fontSize: 12, color: '#cf222e', marginTop: -4, marginBottom: 12 }}>{folderParseError}</p>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 16 }}>
        {effectiveFolderId && (
          <a
            href={driveFolderUrl(effectiveFolderId)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: '#0969da' }}
          >
            Open in Drive
          </a>
        )}
        {showResetInbox && (
          <button type="button" onClick={resetToTeamInbox} style={btnSecondary}>
            Reset to team inbox
          </button>
        )}
        <button type="button" onClick={() => listMutation.mutate()} disabled={listMutation.isPending} style={btnPrimary}>
          {listMutation.isPending ? 'Listing…' : 'List files'}
        </button>
        <button
          type="button"
          onClick={() => {
            if (!canIngestQuick) {
              if (
                !window.confirm(
                  'No folder and nothing selected — ingest may scan all of Drive. Continue?',
                )
              )
                return
            }
            ingestMutation.mutate()
          }}
          disabled={ingestMutation.isPending}
          style={btnPrimary}
        >
          {ingestMutation.isPending
            ? batchStatus
              ? formatBatchProgress(batchStatus)
              : 'Queuing…'
            : 'Ingest'}
        </button>
      </div>

      {!canIngestQuick && (
        <p style={{ fontSize: 12, color: '#57606a', marginBottom: 12 }}>
          Select files below or configure a folder (team inbox or paste a link).
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
          {files.map(f => {
            const isIndexed = f.index_status === 'indexed'
            return (
              <label
                key={f.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 12px',
                  borderBottom: '1px solid #f0f0f0',
                  fontSize: 13,
                  opacity: isIndexed ? 0.75 : 1,
                }}
              >
                <input type="checkbox" checked={selected.has(f.id)} onChange={() => toggle(f.id)} />
                <span style={{ flex: 1 }}>
                  {f.name || f.id}
                  {driveFileTypeLabel(f.mimeType) ? (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 11,
                        color: '#57606a',
                        fontWeight: 600,
                      }}
                    >
                      {driveFileTypeLabel(f.mimeType)}
                    </span>
                  ) : null}
                </span>
                <IndexStatusBadge file={f} />
              </label>
            )
          })}
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
