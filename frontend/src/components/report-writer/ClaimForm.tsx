import { useState } from 'react'
import type { Claim, PhotoAnalysisCounts, ReportTypeDefinition } from '../../types'
import { AddressFields } from './AddressFields'
import { PhotoFolderPanel } from './PhotoFolderPanel'
import { PropertyMapPreview } from './PropertyMapPreview'
import { StormPicker } from './StormPicker'
import { WeatherPicker } from './WeatherPicker'
import type { WeatherOptionsResponse, PropertyMapResponse } from '../../types'

const inputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: 8,
  borderRadius: 6,
  border: '1px solid var(--app-border)',
}

const stepLegend: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--app-primary)',
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
  onUploadBatchStarted,
  weatherLoading,
  weatherError,
  weatherOptions,
  onRefreshWeather,
  onWeatherSelectionChange,
  propertyMapLoading,
  propertyMapError,
  propertyMapPreview,
  onRefreshPropertyMap,
  canGenerate = false,
  generating = false,
  onGenerate,
  generateTitle,
}: {
  claim: Claim
  claimId: string | null
  reportTypes: ReportTypeDefinition[]
  typeLocked?: boolean
  onChange: (patch: Partial<Pick<Claim, 'title' | 'field_notes' | 'property_metadata'>>) => void
  onConfirmPhotoSync: () => void
  photoSyncing: boolean
  photoSyncError: string | null
  photoCounts?: PhotoAnalysisCounts | null
  onUploadBatchStarted?: (batchId: string) => void
  weatherLoading?: boolean
  weatherError?: string | null
  weatherOptions?: WeatherOptionsResponse | null
  onRefreshWeather?: () => void
  onWeatherSelectionChange?: (patch: Record<string, string>) => void
  propertyMapLoading?: boolean
  propertyMapError?: string | null
  propertyMapPreview?: PropertyMapResponse | null
  onRefreshPropertyMap?: () => void
  canGenerate?: boolean
  generating?: boolean
  onGenerate?: () => void
  generateTitle?: string
}) {
  const meta = claim.property_metadata || {}
  const [stormCustom, setStormCustom] = useState(false)
  const showManualDate = !meta.storm_id || stormCustom
  const selectedType = reportTypes.find(t => t.id === meta.report_type)

  const keepBaseFields = (base: Record<string, string>): Record<string, string> => {
    const next: Record<string, string> = {}
    if (base.report_type) next.report_type = base.report_type
    if (base.address) next.address = base.address
    if (base.address2) next.address2 = base.address2
    if (base.city) next.city = base.city
    if (base.state) next.state = base.state
    if (base.zip) next.zip = base.zip
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
      <div
        style={{
          border: '2px solid var(--app-primary)',
          borderRadius: 8,
          padding: 14,
          margin: 0,
        }}
      >
        <div style={stepLegend}>Step 1 — Property address</div>
        <fieldset
          style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}
          disabled={typeLocked}
        >
          <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--app-text-muted)' }}>
            Start here. We use the address to find the job&apos;s photo folder in Google Drive.
          </p>
          <AddressFields
            value={{
              address: meta.address,
              address2: meta.address2,
              city: meta.city,
              state: meta.state,
              zip: meta.zip,
            }}
            onChange={patch => updateMetadata(patch as Record<string, string>)}
            disabled={typeLocked}
          />
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
        <PropertyMapPreview
          preview={propertyMapPreview ?? null}
          loading={!!propertyMapLoading}
          error={propertyMapError ?? null}
          resolvedAddress={meta.property_map_resolved_address}
          onRefresh={onRefreshPropertyMap ?? (() => {})}
        />
      </div>

      <PhotoFolderPanel
        claimId={claimId ?? ''}
        claim={claim}
        onMetadataChange={updateMetadata}
        onConfirmSync={onConfirmPhotoSync}
        syncing={photoSyncing}
        syncError={photoSyncError}
        photoCounts={photoCounts}
        onUploadBatchStarted={onUploadBatchStarted}
      />

      <fieldset
        style={{
          border: '1px solid var(--app-border)',
          borderRadius: 6,
          padding: 12,
          margin: 0,
        }}
        disabled={typeLocked}
      >
        <legend style={{ ...stepLegend, color: 'var(--app-text)' }}>Step 3 — Report type</legend>
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
                <span style={{ display: 'block', color: 'var(--app-text-muted)', fontSize: 12, marginTop: 2 }}>
                  {type.description}
                </span>
              </span>
            </label>
          ))}
        </div>
        {typeLocked ? (
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>
            Report type is locked after generation.
          </p>
        ) : null}
        {!meta.report_type ? (
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-warning)' }}>
            Select a report type before generating a draft.
          </p>
        ) : null}
      </fieldset>
      {selectedType ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--app-text-muted)' }}>
          {selectedType.sections.length} sections: {selectedType.sections.map(s => s.label).join(', ')}
        </p>
      ) : null}

      <fieldset
        style={{
          border: '1px solid var(--app-border)',
          borderRadius: 6,
          padding: 12,
          margin: 0,
        }}
        disabled={typeLocked}
      >
        <legend style={{ ...stepLegend, color: 'var(--app-text)' }}>Step 4 — Storm &amp; property</legend>
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
        {showManualDate ? (
          <label style={{ fontSize: 13, display: 'block', marginTop: 10 }}>
            <span style={{ display: 'block', marginBottom: 4 }}>Storm date</span>
            <input
              value={meta.storm_date ?? ''}
              onChange={e => updateMetadata({ storm_date: e.target.value })}
              placeholder="e.g. September 28, 2022"
              style={inputStyle}
            />
          </label>
        ) : null}
        <label style={{ fontSize: 13, display: 'block', marginTop: 10 }}>
          <span style={{ display: 'block', marginBottom: 4 }}>Property type</span>
          <input
            value={meta.property_type ?? ''}
            onChange={e => updateMetadata({ property_type: e.target.value })}
            style={inputStyle}
          />
        </label>
        <WeatherPicker
          options={weatherOptions ?? null}
          metadata={meta}
          loading={!!weatherLoading}
          error={weatherError ?? null}
          disabled={typeLocked}
          onRefresh={onRefreshWeather ?? (() => {})}
          onSelectionChange={onWeatherSelectionChange ?? (() => {})}
        />
      </fieldset>

      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600, color: 'var(--app-primary)' }}>
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
        {!claim.field_notes.trim() ? (
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-warning)' }}>
            Add field notes before generating a draft.
          </p>
        ) : null}
      </label>

      <div
        style={{
          marginTop: 4,
          padding: '16px 14px',
          borderTop: '2px solid var(--app-border)',
          borderRadius: 8,
          background: 'var(--app-bg-subtle, rgba(0, 0, 0, 0.02))',
        }}
      >
        <h3 style={{ margin: '0 0 6px', fontSize: 14, color: 'var(--app-primary)' }}>Report sections</h3>
        <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--app-text-muted)', lineHeight: 1.5 }}>
          The sections below are your report draft. Generate them from the steps above, then edit anything you like.
          Generating or regenerating will not overwrite text you have edited.
        </p>
        {onGenerate ? (
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || !canGenerate}
            title={generateTitle}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: 'var(--app-primary)',
              color: 'var(--app-on-primary)',
              cursor: generating || !canGenerate ? 'not-allowed' : 'pointer',
              opacity: generating || !canGenerate ? 0.6 : 1,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {generating ? 'Generating…' : 'Generate draft'}
          </button>
        ) : null}
      </div>
    </div>
  )
}
