import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { cancelIngestBatch, driveGetFolder, driveListFiles, driveTest, ingestGoogleDrive, pollIngestBatch } from '../../api/drive'
import { useAuth } from '../../context/AuthContext'
import { apiOrigin } from '../../lib/api'
import {
  DRIVE_FOLDER_STORAGE_KEY,
  DRIVE_STEPS_OPEN_STORAGE_KEY,
  driveFolderUrl,
  parseDriveFolderInput,
  resolveDriveFolderForApi,
} from '../../lib/driveFolder'
import type { DriveFileListSummary, DriveFileMeta, DriveFolderContext, IngestBatchStatusResponse } from '../../types'

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

function looksLikeAuthError(message: string): boolean {
  return /credentials|token/i.test(message)
}

const detailsStyle: CSSProperties = {
  marginBottom: 14,
  fontSize: 13,
  color: 'var(--app-text)',
}

const detailsSummaryStyle: CSSProperties = {
  cursor: 'pointer',
  color: 'var(--app-primary)',
  fontWeight: 600,
  userSelect: 'none',
}

const detailsBodyStyle: CSSProperties = {
  marginTop: 10,
  paddingLeft: 4,
  lineHeight: 1.6,
  color: 'var(--app-text-muted)',
}

function IndexStatusBadge({ file }: { file: DriveFileMeta }) {
  const status = file.index_status ?? 'not_indexed'
  const styles: Record<string, CSSProperties> = {
    not_indexed: { background: 'var(--app-surface)', color: 'var(--app-text-muted)', border: '1px solid var(--app-border)' },
    indexed: { background: 'var(--app-success-bg)', color: 'var(--app-success)', border: '1px solid var(--app-success-border)' },
    stale: { background: 'var(--app-warning-bg)', color: 'var(--app-warning)', border: '1px solid var(--app-warning-border)' },
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
  const teamInboxLabel = publicConfig?.google_drive_default_folder_label ?? ''
  const [folderInput, setFolderInput] = useState('')
  const [folderParseError, setFolderParseError] = useState('')
  const [files, setFiles] = useState<DriveFileMeta[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [authHelpOpen, setAuthHelpOpen] = useState(false)
  const [stepsOpen, setStepsOpen] = useState(true)
  const base = apiOrigin()
  const queryClient = useQueryClient()
  const initDoneRef = useRef(false)
  const autoListedRef = useRef(false)

  const apiFolderId = () => resolveDriveFolderForApi(folderInput, teamInboxId)
  const effectiveFolderId = apiFolderId()

  const { data: folderContext, isLoading: folderLoading } = useQuery({
    queryKey: ['drive-folder', effectiveFolderId],
    queryFn: () => driveGetFolder(effectiveFolderId),
    enabled: !!effectiveFolderId,
  })

  const folderDisplayPath =
    folderContext?.display_path ??
    (effectiveFolderId === teamInboxId && teamInboxLabel
      ? teamInboxLabel
      : effectiveFolderId)
  const folderIsDefault =
    folderContext?.is_default ??
    (!!teamInboxId && effectiveFolderId === teamInboxId)

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
      if (data.folder && effectiveFolderId) {
        queryClient.setQueryData<DriveFolderContext>(
          ['drive-folder', effectiveFolderId],
          data.folder,
        )
      }
    },
    onError: (e: Error) => {
      setFiles([])
      setSelected(new Set())
      setMsg('')
      setErr(e.message)
    },
  })

  const [batchStatus, setBatchStatus] = useState<IngestBatchStatusResponse | null>(null)
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null)
  const [cancellingIngest, setCancellingIngest] = useState(false)
  const pollStopRef = useRef<(() => void) | null>(null)

  const formatBatchProgress = (s: IngestBatchStatusResponse) =>
    `Ingesting ${s.total} doc(s): ${s.succeeded} done, ${s.pending + s.running} in progress` +
    (s.failed ? `, ${s.failed} failed` : '') +
    (s.skipped ? `, ${s.skipped} skipped` : '') +
    (s.cancelled ? `, ${s.cancelled} cancelled` : '')

  const ingestMutation = useMutation({
    mutationFn: async () => {
      const enqueued = await ingestGoogleDrive({
        folder_id: apiFolderId() ?? null,
        file_ids: selected.size ? Array.from(selected) : null,
      })
      setBatchStatus(null)
      setErr('')
      setMsg(`Queued ${enqueued.total} document(s)…`)
      setActiveBatchId(enqueued.batch_id)
      const { promise, stop } = pollIngestBatch(enqueued.batch_id, status => {
        setBatchStatus(status)
        setMsg(formatBatchProgress(status))
      })
      pollStopRef.current = stop
      return promise
    },
    onSuccess: finalStatus => {
      pollStopRef.current = null
      setActiveBatchId(null)
      setErr('')
      if (finalStatus.status === 'cancelled') {
        const cancelMsg =
          `Ingest cancelled. ${finalStatus.succeeded} indexed before stop` +
          (finalStatus.cancelled ? `; ${finalStatus.cancelled} queued job(s) skipped` : '') +
          '.'
        queryClient.invalidateQueries({ queryKey: ['documents'] })
        listMutation.mutate(undefined, {
          onSuccess: data => {
            setMsg(
              data.summary
                ? `${cancelMsg} ${formatListSummary(data.summary)}`
                : `${cancelMsg} Found ${data.files?.length ?? 0} ingestable file(s).`,
            )
          },
          onError: () => {
            setMsg(cancelMsg)
          },
        })
        setBatchStatus(null)
        return
      }
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
      pollStopRef.current = null
      setActiveBatchId(null)
      setBatchStatus(null)
      setMsg('')
      setErr(e.message)
    },
  })

  const handleCancelIngest = async () => {
    if (!activeBatchId) return
    setCancellingIngest(true)
    try {
      await cancelIngestBatch(activeBatchId)
      pollStopRef.current?.()
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Cancel failed')
    } finally {
      setCancellingIngest(false)
    }
  }

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

  useEffect(() => {
    if (err && looksLikeAuthError(err)) setAuthHelpOpen(true)
  }, [err])

  useEffect(() => {
    const stored = localStorage.getItem(DRIVE_STEPS_OPEN_STORAGE_KEY)
    if (stored !== null) setStepsOpen(stored === '1')
  }, [])

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

  const selectAll = () => setSelected(new Set(files.map(f => f.id)))
  const deselectAll = () => setSelected(new Set())

  const defaultFolderLinkText =
    teamInboxLabel || 'the team ingest folder in Google Drive'

  return (
    <div>
      <h2 style={{ marginTop: 0, color: 'var(--app-primary)', fontSize: 18 }}>Google Drive</h2>

      <p style={{ fontSize: 13, color: 'var(--app-text-muted)', lineHeight: 1.6, marginBottom: 14 }}>
        List and ingest completed reports from Google Drive into the document repository.
      </p>

      <details
        open={stepsOpen}
        onToggle={e => {
          const open = (e.target as HTMLDetailsElement).open
          setStepsOpen(open)
          localStorage.setItem(DRIVE_STEPS_OPEN_STORAGE_KEY, open ? '1' : '0')
        }}
        style={{
          fontSize: 13,
          color: 'var(--app-text)',
          marginBottom: 16,
          padding: '12px 16px',
          background: 'var(--app-surface)',
          border: '1px solid var(--app-border)',
          borderRadius: 8,
          lineHeight: 1.5,
        }}
      >
        <summary style={{ ...detailsSummaryStyle, color: 'var(--app-text)' }}>
          How to ingest your files
        </summary>
        <ol style={{ margin: '10px 0 0', paddingLeft: 20 }}>
          <li style={{ marginBottom: 6 }}>
            <strong>Choose your files.</strong> Open the Drive folder
            {effectiveFolderId ? (
              <>
                {' '}
                (
                <a
                  href={driveFolderUrl(effectiveFolderId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--app-primary)', fontWeight: 600 }}
                >
                  open in Drive
                </a>
                )
              </>
            ) : null}
            , drop your completed report(s) in, then click <strong>List files</strong> to see
            what&rsquo;s there.
          </li>
          <li style={{ marginBottom: 6 }}>
            <strong>Ingest your files.</strong> Select the report(s) you want and click{' '}
            <strong>Ingest</strong>.
          </li>
          <li>
            <strong>Get answers from them.</strong> Once indexed, those files are searched
            automatically whenever you ask a question in the Chat tab, so the assistant can pull
            real answers from them.
          </li>
        </ol>
      </details>

      {teamInboxId ? (
        <p style={{ fontSize: 13, color: 'var(--app-text)', lineHeight: 1.6, marginBottom: 14 }}>
          Our default folder for ingesting completed reports into the repository is{' '}
          <a
            href={driveFolderUrl(teamInboxId)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--app-primary)', fontWeight: 600 }}
          >
            {defaultFolderLinkText}
          </a>
          . You may change selections and ingest from other folders below, but the best procedure is
          to copy your file into that folder first.
        </p>
      ) : (
        <div
          style={{
            ...banner,
            background: 'var(--app-warning-bg)',
            color: 'var(--app-warning)',
            border: '1px solid var(--app-warning-border)',
          }}
        >
          No team ingest folder is configured. An administrator must set{' '}
          <code>GOOGLE_DRIVE_DEFAULT_FOLDER_ID</code> on the server, or paste a folder link below.
        </div>
      )}

      {effectiveFolderId && (
        <div
          style={{
            fontSize: 13,
            color: 'var(--app-text)',
            marginBottom: 12,
            padding: '10px 12px',
            background: 'var(--app-surface)',
            border: '1px solid var(--app-border)',
            borderRadius: 6,
            lineHeight: 1.5,
          }}
        >
          <strong>Folder:</strong>{' '}
          {folderLoading && !folderContext ? 'Loading…' : folderDisplayPath}
          {' · '}
          <span style={{ color: 'var(--app-text-muted)', fontStyle: 'italic' }}>
            {folderIsDefault ? 'Team inbox (default)' : 'Custom folder'}
          </span>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 16 }}>
        {effectiveFolderId && (
          <a
            href={driveFolderUrl(effectiveFolderId)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: 'var(--app-primary)' }}
          >
            Open in Drive
          </a>
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
        {ingestMutation.isPending && activeBatchId ? (
          <button
            type="button"
            onClick={() => void handleCancelIngest()}
            disabled={cancellingIngest}
            style={btnPrimary}
          >
            {cancellingIngest ? 'Cancelling…' : 'Cancel ingest'}
          </button>
        ) : null}
      </div>

      {!canIngestQuick && (
        <p style={{ fontSize: 12, color: 'var(--app-text-muted)', marginBottom: 12 }}>
          Select files below, or open <em>Use a different folder</em> to browse another location.
        </p>
      )}

      {msg && (
        <div style={{ ...banner, background: 'var(--app-success-bg)', color: 'var(--app-success)' }}>
          {msg}
        </div>
      )}
      {err && (
        <div style={{ ...banner, background: 'var(--app-danger-bg)', color: 'var(--app-danger)' }}>
          {err}
        </div>
      )}

      {files.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginTop: 12,
          }}
        >
          <button type="button" onClick={selectAll} style={btnSecondary}>
            Select all
          </button>
          <button type="button" onClick={deselectAll} style={btnSecondary}>
            Deselect all
          </button>
          <span style={{ fontSize: 12, color: 'var(--app-text-muted)', marginLeft: 'auto' }}>
            {selected.size} of {files.length} selected
          </span>
        </div>
      )}

      {files.length > 0 && (
        <div
          style={{
            marginTop: 8,
            maxHeight: 360,
            overflow: 'auto',
            border: '1px solid var(--app-border)',
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
                  borderBottom: '1px solid var(--app-border)',
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
                        color: 'var(--app-text-muted)',
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

      <details style={detailsStyle} open={!teamInboxId}>
        <summary style={detailsSummaryStyle}>Use a different folder</summary>
        <div style={detailsBodyStyle}>
          <label style={{ fontSize: 13, color: 'var(--app-text)', display: 'block', marginBottom: 8 }}>
            Folder link or ID
            <input
              value={folderInput}
              onChange={e => {
                setFolderInput(e.target.value)
                setFolderParseError('')
              }}
              onBlur={commitFolderInput}
              placeholder={
                teamInboxId
                  ? 'Paste drive.google.com/.../folders/… or folder id'
                  : 'Paste drive.google.com/.../folders/… or folder id (required)'
              }
              style={inputStyle}
            />
          </label>
          {folderParseError && (
            <p style={{ fontSize: 12, color: 'var(--app-danger)', marginTop: -4, marginBottom: 12 }}>
              {folderParseError}
            </p>
          )}
          {showResetInbox && (
            <button type="button" onClick={resetToTeamInbox} style={btnSecondary}>
              Reset to team inbox
            </button>
          )}
        </div>
      </details>

      <details
        style={detailsStyle}
        open={authHelpOpen}
        onToggle={e => setAuthHelpOpen((e.target as HTMLDetailsElement).open)}
      >
        <summary style={detailsSummaryStyle}>Connection or setup problems?</summary>
        <div style={detailsBodyStyle}>
          <p style={{ marginTop: 0 }}>
            The API reads Drive using server credentials (<code>GOOGLE_REFRESH_TOKEN</code> and client
            id/secret). To obtain a refresh token, open{' '}
            <a href={`${base}/auth/google`} target="_blank" rel="noopener noreferrer">
              /auth/google
            </a>{' '}
            in your browser while the API origin matches <code>GOOGLE_REDIRECT_URI</code>; copy the
            shown value into your environment.
          </p>
          <p style={{ marginBottom: 12 }}>
            Supported file types: Google Docs, PDF, and Word (.docx). Max download size 100 MB per
            file.
          </p>
          <button
            type="button"
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
            style={btnSecondary}
          >
            {testMutation.isPending ? 'Testing…' : 'Test credentials'}
          </button>
        </div>
      </details>
    </div>
  )
}

const btnPrimary: CSSProperties = {
  background: 'var(--app-primary)',
  color: 'var(--app-on-primary)',
  border: 'none',
  borderRadius: 6,
  padding: '8px 16px',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
}

const btnSecondary: CSSProperties = {
  ...btnPrimary,
  background: 'var(--app-surface)',
  color: 'var(--app-text)',
  border: '1px solid var(--app-border)',
}

const inputStyle: CSSProperties = {
  display: 'block',
  width: '100%',
  marginTop: 6,
  boxSizing: 'border-box',
  padding: '8px 12px',
  borderRadius: 6,
  border: '1px solid var(--app-border)',
  fontSize: 13,
}

const banner: CSSProperties = {
  borderRadius: 6,
  padding: '10px 14px',
  fontSize: 13,
  marginBottom: 12,
}
