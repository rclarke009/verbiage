import { useCallback, useEffect, useRef, useState } from 'react'

import { apiOrigin, getAuthFetchInit } from '../../lib/api'
import type { HistoricalAerialItem, HistoricalAerialsResponse } from '../../types'

function joinUrl(origin: string, path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!origin) return p
  return `${origin.replace(/\/$/, '')}${p}`
}

function AerialThumb({
  item,
  onLoadFailed,
  onIncludeChange,
  disabled,
}: {
  item: HistoricalAerialItem
  onLoadFailed?: () => void
  onIncludeChange: (include: boolean) => void
  disabled?: boolean
}) {
  const [src, setSrc] = useState(item.preview || '')
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(!item.preview && !!item.image_url)
  const onLoadFailedRef = useRef(onLoadFailed)
  onLoadFailedRef.current = onLoadFailed

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false

    async function load() {
      if (item.preview) {
        setSrc(item.preview)
        setFailed(false)
        setLoading(false)
        return
      }
      if (!item.image_url) {
        setSrc('')
        setFailed(true)
        setLoading(false)
        return
      }
      setLoading(true)
      setFailed(false)
      setSrc('')
      try {
        const init = await getAuthFetchInit({ method: 'GET' })
        const res = await fetch(joinUrl(apiOrigin(), item.image_url), init)
        if (!res.ok) throw new Error('Failed to load aerial image')
        const blob = await res.blob()
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
        setFailed(false)
        setLoading(false)
      } catch {
        if (!cancelled) {
          setFailed(true)
          setLoading(false)
          setSrc('')
          onLoadFailedRef.current?.()
        }
      }
    }

    void load()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [item.preview, item.image_url, item.year])

  return (
    <figure style={{ margin: 0, flex: '1 1 140px', maxWidth: 200 }}>
      <div
        style={{
          position: 'relative',
          borderRadius: 6,
          border: '1px solid var(--app-border)',
          overflow: 'hidden',
          background: 'var(--app-bg-subtle, rgba(0,0,0,0.03))',
          minHeight: 100,
        }}
      >
        {loading ? (
          <p style={{ margin: 0, padding: 24, fontSize: 12, color: 'var(--app-text-muted)', textAlign: 'center' }}>
            Loading…
          </p>
        ) : null}
        {failed && !loading ? (
          <p style={{ margin: 0, padding: 24, fontSize: 12, color: 'var(--app-text-muted)', textAlign: 'center' }}>
            Unavailable
          </p>
        ) : null}
        {src && !failed ? (
          <img
            src={src}
            alt={`NAIP ${item.year}`}
            onError={() => {
              setFailed(true)
              setSrc('')
            }}
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
        ) : null}
      </div>
      <figcaption style={{ marginTop: 6, fontSize: 12 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: disabled ? 'default' : 'pointer' }}>
          <input
            type="checkbox"
            checked={!!item.include}
            disabled={disabled || failed}
            onChange={e => onIncludeChange(e.target.checked)}
          />
          <span style={{ fontWeight: 600 }}>{item.year}</span>
          <span style={{ color: 'var(--app-text-muted)' }}>Include</span>
        </label>
      </figcaption>
    </figure>
  )
}

export function HistoricalAerialsPreview({
  preview,
  loading,
  error,
  disabled,
  onRefresh,
  onCachedImagesUnavailable,
  onIncludeChange,
  onCommentChange,
}: {
  preview: HistoricalAerialsResponse | null
  loading: boolean
  error: string | null
  disabled?: boolean
  onRefresh: () => void
  onCachedImagesUnavailable?: () => void
  onIncludeChange: (year: number, include: boolean) => void
  onCommentChange: (comment: string) => void
}) {
  const staleRetryKeyRef = useRef<string | null>(null)
  const refreshInFlightRef = useRef(false)
  const lastFetchKeyRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    const key = preview?.fetch_key
    if (key !== lastFetchKeyRef.current) {
      lastFetchKeyRef.current = key
      staleRetryKeyRef.current = null
      refreshInFlightRef.current = false
    }
  }, [preview?.fetch_key])

  useEffect(() => {
    if (!loading) refreshInFlightRef.current = false
  }, [loading])

  const handleStaleCache = useCallback(() => {
    if (loading || refreshInFlightRef.current) return
    const key = preview?.fetch_key ?? ''
    if (!key) return
    if (staleRetryKeyRef.current === key) {
      onCachedImagesUnavailable?.()
      return
    }
    staleRetryKeyRef.current = key
    refreshInFlightRef.current = true
    onRefresh()
  }, [loading, onCachedImagesUnavailable, onRefresh, preview?.fetch_key])

  const aerials = preview?.aerials ?? []
  const anyIncluded = aerials.some(a => a.include)
  const showStrip = aerials.length > 0

  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Historical aerials (NAIP)</span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || disabled}
          style={{
            fontSize: 12,
            padding: '4px 8px',
            borderRadius: 6,
            border: '1px solid var(--app-border)',
            background: 'var(--app-surface)',
            cursor: loading || disabled ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--app-text-muted)', lineHeight: 1.4 }}>
        Auto-fetched from date of loss through the latest available flight (max 5). Check images to include in
        the export and optionally add a comment.
      </p>
      {error ? (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-danger, #c62828)' }}>{error}</p>
      ) : null}
      {!error && loading && !showStrip ? (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>
          Fetching historical aerials…
        </p>
      ) : null}
      {showStrip ? (
        <>
          <div style={{ display: 'flex', gap: 10, marginTop: 10, flexWrap: 'wrap' }}>
            {aerials.map(item => (
              <AerialThumb
                key={item.year}
                item={item}
                disabled={disabled}
                onIncludeChange={include => onIncludeChange(item.year, include)}
                onLoadFailed={handleStaleCache}
              />
            ))}
          </div>
          <label style={{ display: 'block', marginTop: 12, fontSize: 13 }}>
            <span style={{ display: 'block', marginBottom: 4 }}>
              Comment for report{anyIncluded ? '' : ' (select images to include)'}
            </span>
            <textarea
              value={preview?.comment ?? ''}
              onChange={e => onCommentChange(e.target.value)}
              disabled={disabled || !anyIncluded}
              rows={3}
              placeholder="e.g. Roof and tree canopy appear unchanged between 2021 and 2023 NAIP flights."
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: 8,
                borderRadius: 6,
                border: '1px solid var(--app-border)',
                fontFamily: 'inherit',
                resize: 'vertical',
                opacity: anyIncluded ? 1 : 0.7,
              }}
            />
          </label>
          <p style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--app-text-muted)' }}>
            {preview?.resolved_address ? `${preview.resolved_address} · ` : ''}
            {preview?.attribution?.[0] ?? 'NAIP / USGS The National Map / USDA'}
          </p>
        </>
      ) : null}
    </div>
  )
}
