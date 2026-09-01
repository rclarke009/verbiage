import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchPropertyAppraiser, updateClaim } from '../api/reportWriter'
import type { ClaimPropertyMetadata, PropertyAppraiserResponse } from '../types'

const DEBOUNCE_MS = 600
const MIN_ADDRESS_LEN = 10

const PROPERTY_APPRAISER_META_KEYS = [
  'property_appraiser_fetch_key',
  'property_appraiser_resolved_address',
  'property_appraiser_county',
  'property_appraiser_fetched_at',
  'property_appraiser_path',
  'property_appraiser_source_url',
  'property_appraiser_parcel_id',
  'property_appraiser_owner',
  'property_appraiser_site_address',
  'property_appraiser_use_code',
  'property_appraiser_acreage',
  'property_appraiser_legal',
] as const

function normalizeAddress(address: string): string {
  return address.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function propertyAppraiserFetchKey(address: string): string {
  return normalizeAddress(address)
}

function basePatchFromResponse(response: PropertyAppraiserResponse): Record<string, string> {
  return {
    property_appraiser_fetch_key: response.fetch_key,
    property_appraiser_resolved_address: response.resolved_address,
    property_appraiser_county: response.county,
    property_appraiser_fetched_at: new Date().toISOString(),
    ...(response.property_appraiser_path
      ? { property_appraiser_path: response.property_appraiser_path }
      : {}),
    ...(response.source_url ? { property_appraiser_source_url: response.source_url } : {}),
    ...(response.parcel_id ? { property_appraiser_parcel_id: response.parcel_id } : {}),
    ...(response.owner ? { property_appraiser_owner: response.owner } : {}),
    ...(response.site_address ? { property_appraiser_site_address: response.site_address } : {}),
    ...(response.use_code ? { property_appraiser_use_code: response.use_code } : {}),
    ...(response.acreage ? { property_appraiser_acreage: response.acreage } : {}),
    ...(response.legal ? { property_appraiser_legal: response.legal } : {}),
  }
}

export function clearPropertyAppraiserMetadata(meta: ClaimPropertyMetadata): ClaimPropertyMetadata {
  const next = { ...meta }
  for (const key of PROPERTY_APPRAISER_META_KEYS) {
    delete next[key]
  }
  return next
}

export function usePropertyAppraiser({
  claimId,
  address,
  metadata,
  onMetadataPatch,
  onPropertyAppraiserClear,
}: {
  claimId: string | null
  address: string
  metadata: ClaimPropertyMetadata
  onMetadataPatch: (patch: Record<string, string>) => void
  onPropertyAppraiserClear?: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PropertyAppraiserResponse | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)
  const prevAddressRef = useRef(address)
  const deadImageKeysRef = useRef<Set<string>>(new Set())
  const previewRef = useRef(preview)
  previewRef.current = preview

  const isCurrent = useCallback(
    (addr: string) => metadata.property_appraiser_fetch_key === propertyAppraiserFetchKey(addr),
    [metadata.property_appraiser_fetch_key],
  )

  const persistPatch = useCallback(
    async (patch: Record<string, string>) => {
      onMetadataPatch(patch)
      if (!claimId) return
      const merged: ClaimPropertyMetadata = {}
      for (const [k, v] of Object.entries(metadata)) {
        if (typeof v === 'string' || Array.isArray(v)) merged[k] = v
      }
      for (const [k, v] of Object.entries(patch)) {
        if (v === '') delete merged[k]
        else if (v !== undefined) merged[k] = v
      }
      await updateClaim(claimId, { property_metadata: merged }).catch(() => {
        /* persist is best-effort */
      })
    },
    [claimId, metadata, onMetadataPatch],
  )

  const fetchPage = useCallback(
    async (force = false) => {
      const addr = address.trim()
      if (addr.length < MIN_ADDRESS_LEN) return

      const fetchKey = metadata.property_appraiser_fetch_key ?? ''
      const imagesDead = fetchKey !== '' && deadImageKeysRef.current.has(fetchKey)

      if (!force && isCurrent(addr) && metadata.property_appraiser_path) {
        const prev = previewRef.current
        const sameKey = prev?.fetch_key === fetchKey
        const previewSrc = sameKey && prev?.preview ? prev.preview : ''
        const attachUrl = !imagesDead && !!claimId
        setPreview({
          resolved_address: metadata.property_appraiser_resolved_address ?? '',
          latitude: metadata.property_latitude ? Number(metadata.property_latitude) : null,
          longitude: metadata.property_longitude ? Number(metadata.property_longitude) : null,
          county: metadata.property_appraiser_county ?? '',
          fetch_key: fetchKey,
          image_url: attachUrl ? `/report-writer/claims/${claimId}/property-appraiser/image` : null,
          property_appraiser_path: metadata.property_appraiser_path,
          preview: previewSrc,
          source_url: metadata.property_appraiser_source_url ?? '',
          parcel_id: metadata.property_appraiser_parcel_id ?? '',
          owner: metadata.property_appraiser_owner ?? '',
          site_address: metadata.property_appraiser_site_address ?? '',
          use_code: metadata.property_appraiser_use_code ?? '',
          acreage: metadata.property_appraiser_acreage ?? '',
          legal: metadata.property_appraiser_legal ?? '',
          attribution: ['County property appraiser public records'],
        })
        if (imagesDead && !previewSrc) {
          setError('Property appraiser image unavailable. Use Refresh to re-fetch.')
        }
        return
      }

      const reqId = ++requestIdRef.current
      setLoading(true)
      setError(null)

      try {
        const response = await fetchPropertyAppraiser(addr, claimId ?? undefined, force)
        if (reqId !== requestIdRef.current) return
        if (response.fetch_key) {
          deadImageKeysRef.current.delete(response.fetch_key)
        }
        setPreview(response)
        if (claimId) {
          await persistPatch(basePatchFromResponse(response))
        }
      } catch (err) {
        if (reqId !== requestIdRef.current) return
        setPreview(null)
        setError(err instanceof Error ? err.message : 'Property appraiser fetch failed')
      } finally {
        if (reqId === requestIdRef.current) {
          setLoading(false)
        }
      }
    },
    [address, claimId, isCurrent, metadata, persistPatch],
  )

  const refresh = useCallback(() => {
    void fetchPage(true)
  }, [fetchPage])

  const markCachedImagesUnavailable = useCallback(() => {
    const key = previewRef.current?.fetch_key
    if (!key) return
    deadImageKeysRef.current.add(key)
    setPreview(prev => (prev ? { ...prev, image_url: null } : prev))
    setError('Property appraiser image unavailable. Use Refresh to re-fetch.')
  }, [])

  useEffect(() => {
    if (prevAddressRef.current !== address) {
      prevAddressRef.current = address
      if (metadata.property_appraiser_fetch_key && !isCurrent(address.trim())) {
        onPropertyAppraiserClear?.()
        setPreview(null)
        setError(null)
      }
    }
  }, [address, isCurrent, metadata.property_appraiser_fetch_key, onPropertyAppraiserClear])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const addr = address.trim()
    if (addr.length < MIN_ADDRESS_LEN) {
      setError(null)
      return
    }

    if (isCurrent(addr) && metadata.property_appraiser_path) {
      void fetchPage(false)
      return
    }

    debounceRef.current = setTimeout(() => {
      void fetchPage(false)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [address, claimId, fetchPage, isCurrent, metadata.property_appraiser_path])

  return {
    loading,
    error,
    refresh,
    preview,
    hasPersisted: !!metadata.property_appraiser_path,
    markCachedImagesUnavailable,
  }
}
