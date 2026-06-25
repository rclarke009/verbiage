import { useEffect, useState } from 'react'

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
}: {
  label: string
  previewSrc: string
  urlPath: string | null | undefined
}) {
  const [src, setSrc] = useState(previewSrc)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false

    async function load() {
      if (previewSrc) {
        setSrc(previewSrc)
        setFailed(false)
        return
      }
      if (!urlPath) {
        setFailed(true)
        return
      }
      try {
        const init = await getAuthFetchInit({ method: 'GET' })
        const res = await fetch(joinUrl(apiOrigin(), urlPath), init)
        if (!res.ok) throw new Error('Failed to load map image')
        const blob = await res.blob()
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
        setFailed(false)
      } catch {
        if (!cancelled) setFailed(true)
      }
    }

    void load()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [previewSrc, urlPath])

  return (
    <figure style={{ margin: 0, flex: 1, minWidth: 0 }}>
      <figcaption style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>{label}</figcaption>
      {failed ? (
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
          Map preview unavailable
        </div>
      ) : (
        <img
          src={src}
          alt={label}
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
  disabled,
}: {
  preview: PropertyMapResponse | null
  loading: boolean
  error: string | null
  resolvedAddress?: string
  onRefresh: () => void
  disabled?: boolean
}) {
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
          disabled={disabled || loading}
          style={{
            fontSize: 12,
            padding: '4px 8px',
            borderRadius: 6,
            border: '1px solid var(--app-border)',
            background: 'var(--app-surface)',
            cursor: disabled || loading ? 'not-allowed' : 'pointer',
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
            />
            <MapImage
              label="Road map"
              previewSrc={preview.roadmap_preview}
              urlPath={preview.roadmap_url}
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
