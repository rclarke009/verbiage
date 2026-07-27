import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { listClaimImages, uploadClaimImage } from '../../api/reportWriter'
import { useAddressFolderMatch } from '../../hooks/useAddressFolderMatch'
import { composeFullAddress, type StructuredAddress } from '../../lib/address'
import {
  addDrivePhotoFolder,
  displayDriveFolderLabel,
  normalizeDrivePhotoFolders,
  parseAndLinkFolder,
  removeDrivePhotoFolder,
  replaceDrivePhotoFolder,
} from '../../lib/drivePhotoFolders'
import { driveFolderUrl } from '../../lib/driveFolder'
import type { Claim, PhotoAnalysisCounts, PropertyMetadata } from '../../types'

const stepLegend: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--app-primary)',
  margin: '0 0 8px',
}

const MIN_FOLDER_MATCH_SCORE = 0.7

type LinkMode = { kind: 'idle' } | { kind: 'add' } | { kind: 'change'; index: number }

export function PhotoFolderPanel({
  claimId,
  claim,
  onMetadataChange,
  onConfirmSync,
  syncing,
  syncError,
  photoCounts,
  onUploadBatchStarted,
}: {
  claimId: string
  claim: Claim
  onMetadataChange: (patch: PropertyMetadata) => void
  onConfirmSync: () => void
  syncing: boolean
  syncError: string | null
  photoCounts?: PhotoAnalysisCounts | null
  onUploadBatchStarted?: (batchId: string) => void
}) {
  const meta = claim.property_metadata || {}
  const address = composeFullAddress(meta as StructuredAddress)
  const folders = normalizeDrivePhotoFolders(meta)
  const hasFolders = folders.length > 0
  const { matches, suggestedId, status: matchStatus, error: matchError } = useAddressFolderMatch(address)
  const visibleMatches = matches.filter(m => m.score >= MIN_FOLDER_MATCH_SCORE)
  const possibleMatch =
    !suggestedId && visibleMatches.length === 1 ? visibleMatches[0] : null
  const [manualInput, setManualInput] = useState('')
  const [manualError, setManualError] = useState('')
  const [linkMode, setLinkMode] = useState<LinkMode>({ kind: 'idle' })
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const imagesQuery = useQuery({
    queryKey: ['claim-images', claimId],
    queryFn: () => listClaimImages(claimId),
    enabled: !!claimId,
  })

  const showLinker = !hasFolders || linkMode.kind !== 'idle'

  const applyFolder = (id: string, name: string) => {
    if (linkMode.kind === 'change') {
      onMetadataChange(replaceDrivePhotoFolder(meta, linkMode.index, id, name))
    } else {
      onMetadataChange(addDrivePhotoFolder(meta, id, name))
    }
    setLinkMode({ kind: 'idle' })
    setManualInput('')
    setManualError('')
  }

  const applySuggested = () => {
    if (!suggestedId) return
    const match = matches.find(m => m.id === suggestedId)
    if (match) applyFolder(match.id, match.name)
  }

  const applyManual = () => {
    const parsed = parseAndLinkFolder(manualInput)
    if ('error' in parsed) {
      setManualError(parsed.error)
      return
    }
    setManualError('')
    applyFolder(parsed.id, parsed.label)
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    e.target.value = ''
    if (!files.length) return
    setUploading(true)
    setUploadError(null)
    let lastBatchId: string | null = null
    try {
      for (const file of files) {
        const result = await uploadClaimImage(claimId, file)
        if (result.batch_id) lastBatchId = result.batch_id
      }
      await imagesQuery.refetch()
      if (lastBatchId) onUploadBatchStarted?.(lastBatchId)
    } catch (err) {
      console.log('MYDEBUG →', err)
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const images = imagesQuery.data ?? []
  const examined = photoCounts?.succeeded ?? images.filter(i => i.analysis_status === 'succeeded').length
  const withDamage = photoCounts?.with_damage ?? 0

  const linkButtonStyle: React.CSSProperties = {
    padding: '6px 12px',
    borderRadius: 6,
    border: '1px solid var(--app-border)',
    background: 'var(--app-surface)',
    cursor: 'pointer',
    fontSize: 13,
  }

  return (
    <fieldset
      style={{
        border: '2px solid var(--app-primary)',
        borderRadius: 8,
        padding: 14,
        margin: 0,
        background: 'var(--app-surface)',
      }}
    >
      <legend style={{ ...stepLegend, padding: '0 6px' }}>Step 2 — Job photos (link Drive folder first)</legend>
      <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--app-text-muted)', lineHeight: 1.5 }}>
        After you enter the address above, we search your jobs folder in Drive. Confirm the match to start
        analyzing photos while you write field notes. You can change a mistyped link or add another folder.
      </p>

      {hasFolders ? (
        <div style={{ marginBottom: 10 }}>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
            {folders.map((folder, index) => {
              const folderUrl = driveFolderUrl(folder.id)
              return (
                <li
                  key={`${folder.id}-${index}`}
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    alignItems: 'center',
                    marginBottom: 8,
                    fontSize: 13,
                  }}
                >
                  <span>
                    Linked folder: <strong>{displayDriveFolderLabel(folder)}</strong>{' '}
                    <a href={folderUrl} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
                      Open in Drive
                    </a>
                  </span>
                  <button
                    type="button"
                    style={linkButtonStyle}
                    onClick={() => {
                      setLinkMode({ kind: 'change', index })
                      setManualInput('')
                      setManualError('')
                    }}
                  >
                    Change
                  </button>
                  <button
                    type="button"
                    style={linkButtonStyle}
                    onClick={() => {
                      onMetadataChange(removeDrivePhotoFolder(meta, index))
                      setLinkMode({ kind: 'idle' })
                    }}
                  >
                    Remove
                  </button>
                </li>
              )
            })}
          </ul>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <button
              type="button"
              style={linkButtonStyle}
              onClick={() => {
                setLinkMode({ kind: 'add' })
                setManualInput('')
                setManualError('')
              }}
            >
              Add another folder
            </button>
            <button
              type="button"
              disabled={syncing}
              onClick={onConfirmSync}
              style={{
                padding: '8px 14px',
                borderRadius: 6,
                border: 'none',
                background: 'var(--app-success)',
                color: 'var(--app-on-primary)',
                cursor: syncing ? 'wait' : 'pointer',
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {syncing ? 'Starting analysis…' : 'Confirm & start analysis'}
            </button>
          </div>
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>
            Removing a folder unlinks it only — photos already pulled in stay on this claim.
          </p>
        </div>
      ) : null}

      {showLinker ? (
        <>
          {linkMode.kind === 'change' ? (
            <p style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--app-text-muted)' }}>
              Paste or pick a replacement for folder {linkMode.index + 1}.
            </p>
          ) : null}
          {linkMode.kind === 'add' ? (
            <p style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--app-text-muted)' }}>
              Link an additional Drive folder. Photos from all linked folders are analyzed together.
            </p>
          ) : null}

          {matchStatus === 'searching' && (
            <p style={{ fontSize: 13, color: 'var(--app-text-muted)', margin: '0 0 8px' }}>
              Searching Drive for this address…
            </p>
          )}
          {matchError && (
            <p style={{ fontSize: 13, color: 'var(--app-danger)', margin: '0 0 8px' }}>{matchError}</p>
          )}

          {suggestedId && matchStatus === 'done' && (
            <div
              style={{
                padding: 10,
                borderRadius: 6,
                background: 'var(--app-info-bg)',
                border: '1px solid var(--app-info-border)',
                marginBottom: 10,
              }}
            >
              <p style={{ margin: 0, fontSize: 13 }}>
                Found job folder:{' '}
                <strong>{matches.find(m => m.id === suggestedId)?.name ?? suggestedId}</strong>
              </p>
              <button
                type="button"
                onClick={applySuggested}
                style={{
                  marginTop: 8,
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: 'none',
                  background: 'var(--app-primary)',
                  color: 'var(--app-on-primary)',
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                Use this folder
              </button>
            </div>
          )}

          {possibleMatch && matchStatus === 'done' && (
            <div
              style={{
                padding: 10,
                borderRadius: 6,
                background: 'var(--app-warning-bg)',
                border: '1px solid var(--app-warning-border)',
                marginBottom: 10,
              }}
            >
              <p style={{ margin: 0, fontSize: 13 }}>
                Possible match ({Math.round(possibleMatch.score * 100)}%):{' '}
                <strong>{possibleMatch.name}</strong>
              </p>
              <button
                type="button"
                onClick={() => applyFolder(possibleMatch.id, possibleMatch.name)}
                style={{
                  marginTop: 8,
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: 'none',
                  background: 'var(--app-primary)',
                  color: 'var(--app-on-primary)',
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                Use this folder
              </button>
            </div>
          )}

          {matchStatus === 'done' && visibleMatches.length > 1 && (
            <div style={{ marginBottom: 10 }}>
              <p style={{ fontSize: 13, margin: '0 0 6px' }}>Multiple folders match — pick one:</p>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {visibleMatches.map(m => (
                  <li key={m.id} style={{ marginBottom: 4 }}>
                    <button
                      type="button"
                      onClick={() => applyFolder(m.id, m.name)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--app-primary)',
                        cursor: 'pointer',
                        padding: 0,
                      }}
                    >
                      {m.name}
                    </button>{' '}
                    <span style={{ color: 'var(--app-text-muted)' }}>
                      ({Math.round(m.score * 100)}% match)
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {matchStatus === 'done' &&
            visibleMatches.length === 0 &&
            address.trim().length >= 5 &&
            !hasFolders && (
              <p style={{ fontSize: 13, color: 'var(--app-warning)', margin: '0 0 8px' }}>
                No folder found for this address. Paste a folder link below.
              </p>
            )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <input
              value={manualInput}
              onChange={e => setManualInput(e.target.value)}
              placeholder="Paste drive.google.com/.../folders/…"
              style={{
                flex: 1,
                minWidth: 200,
                padding: 8,
                borderRadius: 6,
                border: '1px solid var(--app-border)',
              }}
            />
            <button
              type="button"
              onClick={applyManual}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: '1px solid var(--app-border)',
                cursor: 'pointer',
              }}
            >
              {linkMode.kind === 'change' ? 'Replace folder' : 'Link folder'}
            </button>
            {linkMode.kind !== 'idle' ? (
              <button
                type="button"
                onClick={() => {
                  setLinkMode({ kind: 'idle' })
                  setManualInput('')
                  setManualError('')
                }}
                style={linkButtonStyle}
              >
                Cancel
              </button>
            ) : null}
          </div>
        </>
      ) : null}

      {manualError ? <p style={{ color: 'var(--app-danger)', fontSize: 12 }}>{manualError}</p> : null}
      {syncError ? <p style={{ color: 'var(--app-danger)', fontSize: 12 }}>{syncError}</p> : null}

      {images.length > 0 && (
        <details style={{ marginTop: 10, fontSize: 13 }}>
          <summary style={{ cursor: 'pointer', color: 'var(--app-primary)' }}>
            {images.length} photo{images.length === 1 ? '' : 's'} — {examined} examined
            {examined > 0 ? `, ${withDamage} with damage` : ''}
          </summary>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18, maxHeight: 160, overflow: 'auto' }}>
            {images.slice(0, 30).map(img => (
              <li key={img.image_id} style={{ marginBottom: 4 }}>
                {img.filename}{' '}
                <span style={{ color: 'var(--app-text-muted)' }}>({img.analysis_status ?? 'pending'})</span>
                {img.source_url ? (
                  <>
                    {' '}
                    <a href={img.source_url} target="_blank" rel="noreferrer">
                      Drive
                    </a>
                  </>
                ) : null}
              </li>
            ))}
            {images.length > 30 ? <li>…and {images.length - 30} more</li> : null}
          </ul>
        </details>
      )}

      <p style={{ margin: '12px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>
        Or{' '}
        <button
          type="button"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--app-primary)',
            cursor: uploading ? 'wait' : 'pointer',
            padding: 0,
            opacity: uploading ? 0.7 : 1,
          }}
        >
          {uploading ? 'Uploading…' : 'upload photos manually'}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={e => void handleUpload(e)}
        />
      </p>
      {uploadError ? (
        <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--app-danger)' }}>{uploadError}</p>
      ) : null}
    </fieldset>
  )
}
