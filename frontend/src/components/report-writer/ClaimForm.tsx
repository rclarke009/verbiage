import type { Claim } from '../../types'

export function ClaimForm({
  claim,
  onChange,
}: {
  claim: Claim
  onChange: (patch: Partial<Pick<Claim, 'title' | 'field_notes' | 'property_metadata'>>) => void
}) {
  const meta = claim.property_metadata || {}
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Title / address</span>
        <input
          value={claim.title}
          onChange={e => onChange({ title: e.target.value })}
          style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #d0d7de' }}
        />
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <label style={{ fontSize: 13 }}>
          <span style={{ display: 'block', marginBottom: 4 }}>Property type</span>
          <input
            value={meta.property_type ?? ''}
            onChange={e =>
              onChange({ property_metadata: { ...meta, property_type: e.target.value } })
            }
            style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #d0d7de' }}
          />
        </label>
        <label style={{ fontSize: 13 }}>
          <span style={{ display: 'block', marginBottom: 4 }}>Storm date</span>
          <input
            value={meta.storm_date ?? ''}
            onChange={e =>
              onChange({ property_metadata: { ...meta, storm_date: e.target.value } })
            }
            style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #d0d7de' }}
          />
        </label>
      </div>
      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Field notes</span>
        <textarea
          value={claim.field_notes}
          onChange={e => onChange({ field_notes: e.target.value })}
          rows={8}
          placeholder="Paste inspection notes, damage observations, etc."
          style={{
            width: '100%',
            padding: 8,
            borderRadius: 6,
            border: '1px solid #d0d7de',
            fontFamily: 'inherit',
            resize: 'vertical',
          }}
        />
      </label>
    </div>
  )
}
