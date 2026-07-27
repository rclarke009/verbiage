import { useCallback, useEffect, useRef, useState } from 'react'

import { apiOrigin, getAuthFetchInit } from '../../lib/api'
import type { PropertyMapResponse } from '../../types'

function joinUrl(origin: string, path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!origin) return p
  return `${origin.replace(/\/$/, '')}${p}`
}

function MapImage({
  label,
  previewSrc,
  urlPath,
  onLoadFailed,
}: {
  label: string
  previewSrc: string
  urlPath: string | null | undefined
  onLoadFailed?: () => void
}) {
  const [src, setSrc] = useState(previewSrc)
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(!previewSrc && !!urlPath)
  const onLoadFailedRef = useRef(onLoadFailed)
  onLoadFailedRef.current = onLoadFailed

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false

    async function load() {
      if (previewSrc) {
        setSrc(previewSrc)
        setFailed(false)
        setLoading(false)
        return
      }
      if (!urlPath) {
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
        const res = await fetch(joinUrl(apiOrigin(), urlPath), init)
        if (!res.ok) throw new Error('Failed to load map image')
        const blob = await res.blob()
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
        setFailed(false)
        setLoading(false)
      } catch {
        if (!cancelled) {
          setSrc('')
          setFailed(true)
          setLoading(false)
          // Only treat a real HTTP/network failure as stale-cache signal.
          onLoadFailedRef.current?.()
        }
      }
    }

    void load()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [previewSrc, urlPath])

  const unavailable = (
    <div
      style={{
        border: '1px dashed var(--app-border)',
        borderRadius: 6,
        padding: 24,
        fontSize: 12,
        color: 'var(--app-text-muted)',
        textAlign: 'center',
      }}
    >
      {loading ? 'Loading map…' : 'Map preview unavailable'}
    </div>
  )

  return (
    <figure style={{ margin: 0, flex: 1, minWidth: 0 }}>
      <figcaption style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>{label}</figcaption>
      {failed || loading || !src ? (
        unavailable
      ) : (
        <img
          src={src}
          alt={label}
          onError={() => {
            // Bad blob/data URL only — do not trigger stale-cache refresh.
            setFailed(true)
            setSrc('')
          }}
          style={{
            width: '100%',
            height: 'auto',
            borderRadius: 6,
            border: '1px solid var(--app-border)',
            display: 'block',
          }}
        />
      )}
    </figure>
  )
}

export function PropertyMapPreview({
  preview,
  loading,
  error,
  resolvedAddress,
  onRefresh,
  onCachedImagesUnavailable,
}: {
  preview: PropertyMapResponse | null
  loading: boolean
  error: string | null
  resolvedAddress?: string
  onRefresh: () => void
  onCachedImagesUnavailable?: () => void
}) {
  // Cap auto-refresh to once per fetch_key. Do not reset when preview strings clear.
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
    if (!loading) {
      refreshInFlightRef.current = false
    }
  }, [loading])

  const handleStaleCache = useCallback(() => {
    if (loading || refreshInFlightRef.current) return
    const key = preview?.fetch_key ?? ''
    if (!key) return
    if (staleRetryKeyRef.current === key) {
      // Already refreshed once for this key — stop attaching dead image URLs.
      onCachedImagesUnavailable?.()
      return
    }
    staleRetryKeyRef.current = key
    refreshInFlightRef.current = true
    onRefresh()
  }, [loading, onCachedImagesUnavailable, onRefresh, preview?.fetch_key])

  const showMaps =
    preview &&
    (preview.satellite_preview || preview.roadmap_preview || preview.satellite_url || preview.roadmap_url)

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Property location maps</span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          style={{
            fontSize: 12,
            padding: '4px 8px',
            borderRadius: 6,
            border: '1px solid var(--app-border)',
            background: 'var(--app-surface)',
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      {error ? (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-danger, #c62828)' }}>{error}</p>
      ) : null}
      {!error && loading && !showMaps ? (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>Fetching maps…</p>
      ) : null}
      {showMaps ? (
        <>
          <div style={{ display: 'flex', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
            <MapImage
              label="Satellite"
              previewSrc={preview.satellite_preview}
              urlPath={preview.satellite_url}
              onLoadFailed={handleStaleCache}
            />
            <MapImage
              label="Florida context"
              previewSrc={preview.roadmap_preview}
              urlPath={preview.roadmap_url}
              onLoadFailed={handleStaleCache}
            />
          </div>
          <p style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--app-text-muted)' }}>
            {resolvedAddress || preview.resolved_address}
            {' · '}
            {preview.attribution?.[0] ?? 'Map data © Google'}
          </p>
        </>
      ) : null}
    </div>
  )
}
