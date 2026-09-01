import { useCallback, useEffect, useRef, useState } from 'react'

import { apiOrigin, getAuthFetchInit } from '../../lib/api'
import type { PropertyAppraiserResponse } from '../../types'

function joinUrl(origin: string, path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!origin) return p
  return `${origin.replace(/\/$/, '')}${p}`
}

export function PropertyAppraiserPreview({
  preview,
  loading,
  error,
  onRefresh,
  onCachedImagesUnavailable,
}: {
  preview: PropertyAppraiserResponse | null
  loading: boolean
  error: string | null
  onRefresh: () => void
  onCachedImagesUnavailable?: () => void
}) {
  const [src, setSrc] = useState(preview?.preview ?? '')
  const [failed, setFailed] = useState(false)
  const [imgLoading, setImgLoading] = useState(false)
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

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    const previewSrc = preview?.preview ?? ''
    const urlPath = preview?.image_url

    async function load() {
      if (previewSrc) {
        setSrc(previewSrc)
        setFailed(false)
        setImgLoading(false)
        return
      }
      if (!urlPath) {
        setSrc('')
        setFailed(!!preview)
        setImgLoading(false)
        return
      }
      setImgLoading(true)
      setFailed(false)
      setSrc('')
      try {
        const init = await getAuthFetchInit({ method: 'GET' })
        const res = await fetch(joinUrl(apiOrigin(), urlPath), init)
        if (!res.ok) throw new Error('Failed to load appraiser image')
        const blob = await res.blob()
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
        setFailed(false)
        setImgLoading(false)
      } catch {
        if (!cancelled) {
          setSrc('')
          setFailed(true)
          setImgLoading(false)
          handleStaleCache()
        }
      }
    }

    void load()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [handleStaleCache, preview, preview?.image_url, preview?.preview])

  const showImage = !!src && !failed && !imgLoading
  const details = [preview?.owner, preview?.parcel_id, preview?.use_code].filter(Boolean).join(' · ')

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Property appraiser</span>
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
      {!error && loading && !showImage ? (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>
          Looking up county property appraiser…
        </p>
      ) : null}
      {imgLoading ? (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--app-text-muted)' }}>Loading screenshot…</p>
      ) : null}
      {showImage ? (
        <>
          <img
            src={src}
            alt="County property appraiser parcel page"
            onError={() => {
              setFailed(true)
              setSrc('')
            }}
            style={{
              width: '100%',
              height: 'auto',
              marginTop: 8,
              borderRadius: 6,
              border: '1px solid var(--app-border)',
              display: 'block',
            }}
          />
          <p style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--app-text-muted)' }}>
            {preview?.county ? `${preview.county} County · ` : ''}
            {details || preview?.resolved_address}
            {preview?.source_url ? ` · ${preview.source_url}` : ''}
          </p>
        </>
      ) : null}
    </div>
  )
}
