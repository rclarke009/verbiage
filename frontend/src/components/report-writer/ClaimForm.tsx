import { useState } from 'react'
import type { Claim, ReportTypeDefinition } from '../../types'
import { StormPicker } from './StormPicker'

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: 8,
  borderRadius: 6,
  border: '1px solid #d0d7de',
}

export function ClaimForm({
  claim,
  reportTypes,
  typeLocked = false,
  onChange,
}: {
  claim: Claim
  reportTypes: ReportTypeDefinition[]
  typeLocked?: boolean
  onChange: (patch: Partial<Pick<Claim, 'title' | 'field_notes' | 'property_metadata'>>) => void
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
    return next
  }

  const updateMetadata = (patch: Record<string, string>) => {
    onChange({ property_metadata: { ...meta, ...patch } })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <fieldset
        style={{
          border: '1px solid #d0d7de',
          borderRadius: 6,
          padding: 12,
          margin: 0,
        }}
        disabled={typeLocked}
      >
        <legend style={{ fontSize: 13, fontWeight: 600, padding: '0 4px' }}>Report type</legend>
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
      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Title</span>
        <input
          value={claim.title}
          onChange={e => onChange({ title: e.target.value })}
          placeholder="Claim name or client reference"
          style={inputStyle}
        />
      </label>
      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Address</span>
        <input
          value={meta.address ?? ''}
          onChange={e => updateMetadata({ address: e.target.value })}
          placeholder="412 Gulfview Drive, Tampa, FL"
          style={inputStyle}
        />
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
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
      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Field notes</span>
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
