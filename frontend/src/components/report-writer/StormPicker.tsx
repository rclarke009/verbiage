import {
  getStormById,
  stormMetadataFromSelection,
  stormOptionLabel,
  stormsByYear,
  type FloridaStorm,
} from '../../data/floridaStorms'

export const CUSTOM_STORM_VALUE = '__custom__'

const inputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: 8,
  borderRadius: 6,
  border: '1px solid var(--app-border)',
}

export type StormPickerSelection =
  | { kind: 'storm'; storm: FloridaStorm; metadata: Record<string, string> }
  | { kind: 'custom' }
  | { kind: 'cleared' }

export function StormPicker({
  stormId,
  customMode,
  onSelect,
}: {
  stormId?: string
  customMode: boolean
  onSelect: (selection: StormPickerSelection) => void
}) {
  const selected = stormId ? getStormById(stormId) : undefined
  const grouped = stormsByYear()
  const years = [...grouped.keys()].sort((a, b) => b - a)

  const selectValue = customMode
    ? CUSTOM_STORM_VALUE
    : selected
      ? selected.id
      : ''

  const handleChange = (value: string) => {
    if (value === CUSTOM_STORM_VALUE) {
      onSelect({ kind: 'custom' })
      return
    }
    if (value === '') {
      onSelect({ kind: 'cleared' })
      return
    }
    const storm = getStormById(value)
    if (storm) {
      onSelect({
        kind: 'storm',
        storm,
        metadata: stormMetadataFromSelection(storm),
      })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label style={{ fontSize: 13 }}>
        <span style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Storm</span>
        <select
          value={selectValue}
          onChange={e => handleChange(e.target.value)}
          style={inputStyle}
        >
          <option value="">Select storm…</option>
          {years.map(year => (
            <optgroup key={year} label={String(year)}>
              {(grouped.get(year) ?? []).map(storm => (
                <option key={storm.id} value={storm.id}>
                  {stormOptionLabel(storm)}
                </option>
              ))}
            </optgroup>
          ))}
          <option value={CUSTOM_STORM_VALUE}>Custom / other</option>
        </select>
      </label>

      {selected && !customMode && (
        <div
          style={{
            fontSize: 12,
            padding: '8px 10px',
            borderRadius: 6,
            background: 'var(--app-surface)',
            border: '1px solid var(--app-border)',
            color: 'var(--app-text)',
            lineHeight: 1.5,
          }}
        >
          <strong>{selected.name}</strong> · {selected.landfall_display} · {selected.category} ·{' '}
          {selected.storm_type.replace('_', ' ')} · {selected.landfall_region}
        </div>
      )}
    </div>
  )
}
