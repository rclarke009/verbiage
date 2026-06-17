import type { ClaimPropertyMetadata, WeatherCandidate, WeatherMetric, WeatherOptionsResponse } from '../../types'

const METRIC_LABELS: Record<WeatherMetric, string> = {
  wind_speed: 'Sustained wind',
  wind_gust: 'Wind gusts',
  hail_size: 'Hail size',
  precip: 'Precipitation',
}

const DISPLAY_METRICS: WeatherMetric[] = ['wind_speed', 'wind_gust', 'hail_size']

const TIER_LABELS: Record<number, string> = {
  1: 'Observed',
  2: 'Reported',
  3: 'Interpolated',
  4: 'Model',
}

function formatValue(c: WeatherCandidate): string {
  if (c.metric === 'hail_size') return `${c.value} ${c.unit}`
  if (c.metric === 'precip') return `${c.value} ${c.unit}`
  return `${Math.round(c.value)} mph`
}

function metricValueKey(metric: WeatherMetric): keyof ClaimPropertyMetadata {
  if (metric === 'wind_speed') return 'wind_speed_mph'
  if (metric === 'wind_gust') return 'wind_gust_mph'
  if (metric === 'hail_size') return 'hail_size_in'
  return 'precip_in' as keyof ClaimPropertyMetadata
}

function metricSourceKey(metric: WeatherMetric): keyof ClaimPropertyMetadata {
  return `weather_${metric}_source` as keyof ClaimPropertyMetadata
}

function metricCustomKey(metric: WeatherMetric): keyof ClaimPropertyMetadata {
  if (metric === 'wind_speed') return 'weather_custom_wind_speed'
  if (metric === 'wind_gust') return 'weather_custom_wind_gust'
  if (metric === 'hail_size') return 'weather_custom_hail'
  return 'weather_custom_precip' as keyof ClaimPropertyMetadata
}

export function buildSelectionPatch(
  options: WeatherOptionsResponse,
  selected: Record<string, string>,
  customValues: Partial<Record<WeatherMetric, string>>,
): Record<string, string> {
  const patch: Record<string, string> = {}

  for (const metric of DISPLAY_METRICS) {
    const custom = customValues[metric]?.trim()
    const sourceKey = metricSourceKey(metric)
    const valueKey = metricValueKey(metric)
    const customKey = metricCustomKey(metric)

    if (custom) {
      patch[customKey] = custom
      patch[valueKey] = custom
      patch[sourceKey] = 'custom'
      continue
    }

    const cid = selected[metric]
    if (!cid) {
      patch[valueKey] = ''
      patch[sourceKey] = ''
      patch[customKey] = ''
      continue
    }

    const candidate = options.candidates.find(c => c.id === cid && c.metric === metric)
    if (!candidate) continue

    patch[sourceKey] = cid
    if (metric === 'hail_size') {
      patch[valueKey] = String(candidate.value)
    } else {
      patch[valueKey] = String(Math.round(candidate.value))
    }
    patch[customKey] = ''
  }

  return patch
}

export function WeatherPicker({
  options,
  metadata,
  loading,
  error,
  disabled,
  onRefresh,
  onSelectionChange,
}: {
  options: WeatherOptionsResponse | null
  metadata: ClaimPropertyMetadata
  loading: boolean
  error: string | null
  disabled?: boolean
  onRefresh: () => void
  onSelectionChange: (patch: Record<string, string>) => void
}) {
  const selected: Record<string, string> = {}
  for (const metric of DISPLAY_METRICS) {
    const src = metadata[metricSourceKey(metric)]
    if (src && src !== 'custom') selected[metric] = src
    else if (options?.selected[metric]) selected[metric] = options.selected[metric]
  }

  const customValues: Partial<Record<WeatherMetric, string>> = {
    wind_speed: metadata.weather_custom_wind_speed,
    wind_gust: metadata.weather_custom_wind_gust,
    hail_size: metadata.weather_custom_hail,
  }

  const handleSelect = (metric: WeatherMetric, candidateId: string) => {
    if (!options) return
    const nextSelected = { ...selected, [metric]: candidateId }
    const nextCustom = { ...customValues }
    delete nextCustom[metric]
    onSelectionChange(buildSelectionPatch(options, nextSelected, nextCustom))
  }

  const handleCustom = (metric: WeatherMetric, value: string) => {
    if (!options) return
    const nextCustom = { ...customValues, [metric]: value }
    const nextSelected = { ...selected }
    delete nextSelected[metric]
    onSelectionChange(buildSelectionPatch(options, nextSelected, nextCustom))
  }

  const handleUseRecommendations = () => {
    if (!options) return
    onSelectionChange(buildSelectionPatch(options, options.selected, {}))
  }

  const hasData =
    options &&
    (options.candidates.length > 0 ||
      metadata.wind_speed_mph ||
      metadata.wind_gust_mph ||
      metadata.hail_size_in)

  return (
    <div
      style={{
        marginTop: 10,
        padding: 10,
        borderRadius: 6,
        background: 'var(--app-surface)',
        border: '1px solid var(--app-border)',
        fontSize: 13,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span style={{ fontWeight: 600 }}>Weather data</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {options && options.candidates.length > 0 ? (
            <button
              type="button"
              onClick={handleUseRecommendations}
              disabled={loading || disabled}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                border: '1px solid var(--app-border)',
                background: 'var(--app-bg)',
                cursor: loading || disabled ? 'not-allowed' : 'pointer',
                fontSize: 12,
              }}
            >
              Use recommendations
            </button>
          ) : null}
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading || disabled}
            style={{
              padding: '4px 10px',
              borderRadius: 6,
              border: '1px solid var(--app-border)',
              background: 'var(--app-bg)',
              cursor: loading || disabled ? 'not-allowed' : 'pointer',
              fontSize: 12,
            }}
          >
            {loading ? 'Fetching…' : 'Refresh weather'}
          </button>
        </div>
      </div>

      {loading ? (
        <p style={{ margin: '8px 0 0', color: 'var(--app-text-muted)' }}>
          Loading weather from multiple sources…
        </p>
      ) : null}

      {!loading && !hasData ? (
        <p style={{ margin: '8px 0 0', color: 'var(--app-text-muted)' }}>
          Enter address and storm date to fetch wind, gust, and hail data for the weather section.
        </p>
      ) : null}

      {!loading && options
        ? DISPLAY_METRICS.map(metric => {
            const candidates = options.candidates.filter(c => c.metric === metric)
            if (candidates.length === 0 && !metadata[metricValueKey(metric)]) return null

            const activeId =
              metadata[metricSourceKey(metric)] === 'custom'
                ? 'custom'
                : selected[metric] || options.selected[metric]

            return (
              <div key={metric} style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>{METRIC_LABELS[metric]}</div>
                {candidates.map(c => (
                  <label
                    key={c.id}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 8,
                      marginBottom: 4,
                      cursor: disabled ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name={`weather-${metric}`}
                      checked={activeId === c.id}
                      disabled={disabled}
                      onChange={() => handleSelect(metric, c.id)}
                      style={{ marginTop: 3 }}
                    />
                    <span>
                      <strong>{formatValue(c)}</strong>
                      {' — '}
                      {c.label}
                      {c.recommended ? (
                        <span
                          style={{
                            marginLeft: 6,
                            fontSize: 11,
                            color: 'var(--app-primary)',
                            fontWeight: 600,
                          }}
                        >
                          Recommended
                        </span>
                      ) : null}
                      <span
                        style={{
                          marginLeft: 6,
                          fontSize: 11,
                          color: 'var(--app-text-muted)',
                        }}
                      >
                        {TIER_LABELS[c.tier] ?? `Tier ${c.tier}`}
                      </span>
                    </span>
                  </label>
                ))}
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginTop: 4,
                    cursor: disabled ? 'not-allowed' : 'pointer',
                  }}
                >
                  <input
                    type="radio"
                    name={`weather-${metric}`}
                    checked={activeId === 'custom'}
                    disabled={disabled}
                    onChange={() => handleCustom(metric, customValues[metric] ?? '')}
                    style={{ marginTop: 0 }}
                  />
                  <span>Custom:</span>
                  <input
                    type="text"
                    value={customValues[metric] ?? ''}
                    disabled={disabled}
                    onChange={e => handleCustom(metric, e.target.value)}
                    placeholder={metric === 'hail_size' ? 'inches' : 'mph'}
                    style={{
                      width: 72,
                      padding: '2px 6px',
                      borderRadius: 4,
                      border: '1px solid var(--app-border)',
                    }}
                  />
                </label>
              </div>
            )
          })
        : null}

      {!loading && metadata.weather_resolved_address ? (
        <p style={{ margin: '10px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>
          Resolved: {metadata.weather_resolved_address}
          {metadata.weather_fetched_at
            ? ` · Fetched ${new Date(metadata.weather_fetched_at).toLocaleString()}`
            : ''}
        </p>
      ) : null}

      {!loading && options && options.attribution.length > 0 ? (
        <p style={{ margin: '6px 0 0', fontSize: 11, color: 'var(--app-text-muted)' }}>
          {options.attribution.join(' · ')}
        </p>
      ) : null}

      {error ? (
        <p style={{ margin: '8px 0 0', color: 'var(--app-danger)', fontSize: 12 }}>{error}</p>
      ) : null}
    </div>
  )
}
