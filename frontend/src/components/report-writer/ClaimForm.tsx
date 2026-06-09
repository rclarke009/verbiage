import { useState } from 'react'
import type { Claim, PhotoAnalysisCounts, ReportTypeDefinition } from '../../types'
import { PhotoFolderPanel } from './PhotoFolderPanel'
import { StormPicker } from './StormPicker'

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: 8,
  borderRadius: 6,
  border: '1px solid #d0d7de',
}

const stepLegend: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: '#0969da',
  padding: '0 4px',
}

export function ClaimForm({
  claim,
  claimId,
  reportTypes,
  typeLocked = false,
  onChange,
  onConfirmPhotoSync,
  photoSyncing,
  photoSyncError,
  photoCounts,
}: {
  claim: Claim
  claimId: string
  reportTypes: ReportTypeDefinition[]
  typeLocked?: boolean
  onChange: (patch: Partial<Pick<Claim, 'title' | 'field_notes' | 'property_metadata'>>) => void
  onConfirmPhotoSync: () => void
  photoSyncing: boolean
  photoSyncError: string | null
  photoCounts?: PhotoAnalysisCounts | null
}) {
  const meta = claim.property_metadata || {}
  const [stormCustom, setStormCustom] = useState(false)
  const showManualDate = !meta.storm_id || stormCustom
  const selectedType = reportTypes.find(t => t.id === meta.report_type)

  const keepBaseFields = (base: Record<string, string>): Record<string, string> => {
    const next: Record<string, string> = {}
    if (base.report_type) next.report_type = base.report_type
    if (base.address) next.address = base.address
    if (base.property_type) next.property_type = base.property_type
    if (base.drive_photo_folder_id) next.drive_photo_folder_id = base.drive_photo_folder_id
    if (base.drive_photo_folder_label) next.drive_photo_folder_label = base.drive_photo_folder_label
    return next
  }

  const updateMetadata = (patch: Record<string, string>) => {
    onChange({ property_metadata: { ...meta, ...patch } })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <fieldset
        style={{
          border: '2px solid #0969da',
          borderRadius: 8,
          padding: 14,
          margin: 0,
        }}
        disabled={typeLocked}
      >
        <legend style={stepLegend}>Step 1 — Property address</legend>
        <p style={{ margin: '0 0 10px', fontSize: 13, color: '#57606a' }}>
          Start here. We use the address to find the job&apos;s photo folder in Google Drive.
        </p>
        <label style={{ fontSize: 13 }}>
          <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Address</span>
          <input
            value={meta.address ?? ''}
            onChange={e => updateMetadata({ address: e.target.value })}
            placeholder="412 Gulfview Drive, Tampa, FL"
            style={inputStyle}
          />
        </label>
        <label style={{ fontSize: 13, display: 'block', marginTop: 10 }}>
          <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Title</span>
          <input
            value={claim.title}
            onChange={e => onChange({ title: e.target.value })}
            placeholder="Claim name or client reference"
            style={inputStyle}
          />
        </label>
      </fieldset>

      <PhotoFolderPanel
        claimId={claimId}
        claim={claim}
        onMetadataChange={updateMetadata}
        onConfirmSync={onConfirmPhotoSync}
        syncing={photoSyncing}
        syncError={photoSyncError}
        photoCounts={photoCounts}
      />

      <fieldset
        style={{
          border: '1px solid #d0d7de',
          borderRadius: 6,
          padding: 12,
          margin: 0,
        }}
        disabled={typeLocked}
      >
        <legend style={{ ...stepLegend, color: '#24292f' }}>Step 3 — Report type</legend>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {reportTypes.map(type => (
            <label
              key={type.id}
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'flex-start',
                fontSize: 13,
                cursor: typeLocked ? 'not-allowed' : 'pointer',
              }}
            >
              <input
                type="radio"
                name="report_type"
                value={type.id}
                checked={meta.report_type === type.id}
                onChange={() => updateMetadata({ report_type: type.id })}
                style={{ marginTop: 3 }}
              />
              <span>
                <span style={{ fontWeight: 600 }}>{type.label}</span>
                <span style={{ display: 'block', color: '#57606a', fontSize: 12, marginTop: 2 }}>
                  {type.description}
                </span>
              </span>
            </label>
          ))}
        </div>
        {typeLocked ? (
          <p style={{ margin: '8px 0 0', fontSize: 12, color: '#57606a' }}>
            Report type is locked after generation.
          </p>
        ) : null}
        {!meta.report_type ? (
          <p style={{ margin: '8px 0 0', fontSize: 12, color: '#9a6700' }}>
            Select a report type before generating a draft.
          </p>
        ) : null}
      </fieldset>
      {selectedType ? (
        <p style={{ margin: 0, fontSize: 12, color: '#57606a' }}>
          {selectedType.sections.length} sections: {selectedType.sections.map(s => s.label).join(', ')}
        </p>
      ) : null}

      <fieldset
        style={{
          border: '1px solid #d0d7de',
          borderRadius: 6,
          padding: 12,
          margin: 0,
        }}
        disabled={typeLocked}
      >
        <legend style={{ ...stepLegend, color: '#24292f' }}>Step 4 — Storm &amp; property</legend>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
          <label style={{ fontSize: 13 }}>
            <span style={{ display: 'block', marginBottom: 4 }}>Property type</span>
            <input
              value={meta.property_type ?? ''}
              onChange={e => updateMetadata({ property_type: e.target.value })}
              style={inputStyle}
            />
          </label>
          {showManualDate ? (
            <label style={{ fontSize: 13 }}>
              <span style={{ display: 'block', marginBottom: 4 }}>Storm date</span>
              <input
                value={meta.storm_date ?? ''}
                onChange={e => updateMetadata({ storm_date: e.target.value })}
                placeholder="e.g. September 28, 2022"
                style={inputStyle}
              />
            </label>
          ) : (
            <div />
          )}
        </div>
        <StormPicker
          stormId={meta.storm_id}
          customMode={stormCustom}
          onSelect={selection => {
            if (selection.kind === 'storm') {
              setStormCustom(false)
              onChange({
                property_metadata: {
                  ...keepBaseFields(meta),
                  ...selection.metadata,
                },
              })
              return
            }
            if (selection.kind === 'custom') {
              setStormCustom(true)
              const next = keepBaseFields(meta)
              if (meta.storm_date) next.storm_date = meta.storm_date
              onChange({ property_metadata: next })
              return
            }
            setStormCustom(false)
            onChange({ property_metadata: keepBaseFields(meta) })
          }}
        />
      </fieldset>

      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600, color: '#0969da' }}>
          Step 5 — Field notes
        </span>
        <textarea
          value={claim.field_notes}
          onChange={e => onChange({ field_notes: e.target.value })}
          rows={8}
          placeholder="Paste inspection notes, damage observations, etc."
          style={{
            ...inputStyle,
            fontFamily: 'inherit',
            resize: 'vertical',
          }}
        />
      </label>
    </div>
  )
}
