import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { listClaimImages, uploadClaimImage } from '../../api/reportWriter'
import { useAddressFolderMatch } from '../../hooks/useAddressFolderMatch'
import { driveFolderUrl, parseDriveFolderInput } from '../../lib/driveFolder'
import type { Claim, PhotoAnalysisCounts } from '../../types'

const stepLegend: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: '#0969da',
  margin: '0 0 8px',
}

const MIN_FOLDER_MATCH_SCORE = 0.7

export function PhotoFolderPanel({
  claimId,
  claim,
  onMetadataChange,
  onConfirmSync,
  syncing,
  syncError,
  photoCounts,
}: {
  claimId: string
  claim: Claim
  onMetadataChange: (patch: Record<string, string>) => void
  onConfirmSync: () => void
  syncing: boolean
  syncError: string | null
  photoCounts?: PhotoAnalysisCounts | null
}) {
  const meta = claim.property_metadata || {}
  const address = meta.address ?? ''
  const folderId = meta.drive_photo_folder_id ?? ''
  const folderLabel = meta.drive_photo_folder_label ?? ''
  const { matches, suggestedId, status: matchStatus, error: matchError } = useAddressFolderMatch(address)
  const visibleMatches = matches.filter(m => m.score >= MIN_FOLDER_MATCH_SCORE)
  const possibleMatch =
    !suggestedId && visibleMatches.length === 1 ? visibleMatches[0] : null
  const [manualInput, setManualInput] = useState('')
  const [manualError, setManualError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const imagesQuery = useQuery({
    queryKey: ['claim-images', claimId],
    queryFn: () => listClaimImages(claimId),
    enabled: !!claimId,
  })

  const pickFolder = (id: string, name: string) => {
    onMetadataChange({
      drive_photo_folder_id: id,
      drive_photo_folder_label: name,
    })
  }

  const applySuggested = () => {
    if (!suggestedId) return
    const match = matches.find(m => m.id === suggestedId)
    if (match) pickFolder(match.id, match.name)
  }

  const applyManual = () => {
    const { id, error } = parseDriveFolderInput(manualInput)
    if (!id) {
      setManualError(error ?? 'Could not parse folder')
      return
    }
    setManualError('')
    pickFolder(id, manualInput.trim())
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await uploadClaimImage(claimId, file)
    e.target.value = ''
    imagesQuery.refetch()
  }

  const folderUrl = folderId ? driveFolderUrl(folderId) : null
  const images = imagesQuery.data ?? []
  const examined = photoCounts?.succeeded ?? images.filter(i => i.analysis_status === 'succeeded').length
  const withDamage = photoCounts?.with_damage ?? 0

  return (
    <fieldset
      style={{
        border: '2px solid #0969da',
        borderRadius: 8,
        padding: 14,
        margin: 0,
        background: '#f6f8fa',
      }}
    >
      <legend style={{ ...stepLegend, padding: '0 6px' }}>Step 2 — Job photos (link Drive folder first)</legend>
      <p style={{ margin: '0 0 12px', fontSize: 13, color: '#57606a', lineHeight: 1.5 }}>
        After you enter the address above, we search your jobs folder in Drive. Confirm the match to start
        analyzing photos while you write field notes.
      </p>

      {matchStatus === 'searching' && (
        <p style={{ fontSize: 13, color: '#57606a', margin: '0 0 8px' }}>Searching Drive for this address…</p>
      )}
      {matchError && (
        <p style={{ fontSize: 13, color: '#cf222e', margin: '0 0 8px' }}>{matchError}</p>
      )}

      {suggestedId && !folderId && matchStatus === 'done' && (
        <div
          style={{
            padding: 10,
            borderRadius: 6,
            background: '#ddf4ff',
            border: '1px solid #54aeff',
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
              background: '#0969da',
              color: '#fff',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Use this folder
          </button>
        </div>
      )}

      {possibleMatch && !folderId && matchStatus === 'done' && (
        <div
          style={{
            padding: 10,
            borderRadius: 6,
            background: '#fff8c5',
            border: '1px solid #d4a72c',
            marginBottom: 10,
          }}
        >
          <p style={{ margin: 0, fontSize: 13 }}>
            Possible match ({Math.round(possibleMatch.score * 100)}%):{' '}
            <strong>{possibleMatch.name}</strong>
          </p>
          <button
            type="button"
            onClick={() => pickFolder(possibleMatch.id, possibleMatch.name)}
            style={{
              marginTop: 8,
              padding: '6px 12px',
              borderRadius: 6,
              border: 'none',
              background: '#0969da',
              color: '#fff',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Use this folder
          </button>
        </div>
      )}

      {matchStatus === 'done' && visibleMatches.length > 1 && !folderId && (
        <div style={{ marginBottom: 10 }}>
          <p style={{ fontSize: 13, margin: '0 0 6px' }}>Multiple folders match — pick one:</p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {visibleMatches.map(m => (
              <li key={m.id} style={{ marginBottom: 4 }}>
                <button
                  type="button"
                  onClick={() => pickFolder(m.id, m.name)}
                  style={{ background: 'none', border: 'none', color: '#0969da', cursor: 'pointer', padding: 0 }}
                >
                  {m.name}
                </button>{' '}
                <span style={{ color: '#57606a' }}>({Math.round(m.score * 100)}% match)</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {matchStatus === 'done' && visibleMatches.length === 0 && address.trim().length >= 5 && !folderId && (
        <p style={{ fontSize: 13, color: '#9a6700', margin: '0 0 8px' }}>
          No folder found for this address. Paste a folder link below.
        </p>
      )}

      {folderId ? (
        <div style={{ marginBottom: 10 }}>
          <p style={{ margin: 0, fontSize: 13 }}>
            Linked folder: <strong>{folderLabel || folderId}</strong>
            {folderUrl ? (
              <>
                {' '}
                <a href={folderUrl} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
                  Open in Drive
                </a>
              </>
            ) : null}
          </p>
          <button
            type="button"
            disabled={syncing}
            onClick={onConfirmSync}
            style={{
              marginTop: 8,
              padding: '8px 14px',
              borderRadius: 6,
              border: 'none',
              background: '#1a7f37',
              color: '#fff',
              cursor: syncing ? 'wait' : 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {syncing ? 'Starting analysis…' : 'Confirm & start analysis'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          <input
            value={manualInput}
            onChange={e => setManualInput(e.target.value)}
            placeholder="Paste drive.google.com/.../folders/…"
            style={{ flex: 1, minWidth: 200, padding: 8, borderRadius: 6, border: '1px solid #d0d7de' }}
          />
          <button
            type="button"
            onClick={applyManual}
            style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #d0d7de', cursor: 'pointer' }}
          >
            Link folder
          </button>
        </div>
      )}
      {manualError ? <p style={{ color: '#cf222e', fontSize: 12 }}>{manualError}</p> : null}
      {syncError ? <p style={{ color: '#cf222e', fontSize: 12 }}>{syncError}</p> : null}

      {images.length > 0 && (
        <details style={{ marginTop: 10, fontSize: 13 }}>
          <summary style={{ cursor: 'pointer', color: '#0969da' }}>
            {images.length} photo{images.length === 1 ? '' : 's'} — {examined} examined
            {examined > 0 ? `, ${withDamage} with damage` : ''}
          </summary>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18, maxHeight: 160, overflow: 'auto' }}>
            {images.slice(0, 30).map(img => (
              <li key={img.image_id} style={{ marginBottom: 4 }}>
                {img.filename}{' '}
                <span style={{ color: '#57606a' }}>({img.analysis_status ?? 'pending'})</span>
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

      <p style={{ margin: '12px 0 0', fontSize: 12, color: '#57606a' }}>
        Or{' '}
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          style={{ background: 'none', border: 'none', color: '#0969da', cursor: 'pointer', padding: 0 }}
        >
          upload one photo manually
        </button>
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={handleUpload} />
      </p>
    </fieldset>
  )
}
