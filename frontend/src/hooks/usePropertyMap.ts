import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchPropertyMap, updateClaim } from '../api/reportWriter'
import type { ClaimPropertyMetadata, PropertyMapResponse } from '../types'

const DEBOUNCE_MS = 600
const MIN_ADDRESS_LEN = 10

const PROPERTY_MAP_META_KEYS = [
  'property_map_fetch_key',
  'property_map_resolved_address',
  'property_latitude',
  'property_longitude',
  'property_map_satellite_path',
  'property_map_roadmap_path',
  'property_map_fetched_at',
] as const

function normalizeAddress(address: string): string {
  return address.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function propertyMapFetchKey(address: string): string {
  return normalizeAddress(address)
}

function basePatchFromResponse(response: PropertyMapResponse): Record<string, string> {
  return {
    property_map_fetch_key: response.fetch_key,
    property_map_resolved_address: response.resolved_address,
    property_latitude: response.latitude != null ? String(response.latitude) : '',
    property_longitude: response.longitude != null ? String(response.longitude) : '',
    property_map_fetched_at: new Date().toISOString(),
    ...(response.property_map_satellite_path
      ? { property_map_satellite_path: response.property_map_satellite_path }
      : {}),
    ...(response.property_map_roadmap_path
      ? { property_map_roadmap_path: response.property_map_roadmap_path }
      : {}),
  }
}

export function clearPropertyMapMetadata(meta: ClaimPropertyMetadata): ClaimPropertyMetadata {
  const next = { ...meta }
  for (const key of PROPERTY_MAP_META_KEYS) {
    delete next[key]
  }
  return next
}

export function usePropertyMap({
  claimId,
  address,
  metadata,
  onMetadataPatch,
  onPropertyMapClear,
}: {
  claimId: string | null
  address: string
  metadata: ClaimPropertyMetadata
  onMetadataPatch: (patch: Record<string, string>) => void
  onPropertyMapClear?: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PropertyMapResponse | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)
  const prevAddressRef = useRef(address)
  /** fetch_keys where cached image URLs already 404'd — do not re-attach URLs. */
  const deadImageKeysRef = useRef<Set<string>>(new Set())
  const previewRef = useRef(preview)
  previewRef.current = preview

  const isMapCurrent = useCallback(
    (addr: string) => metadata.property_map_fetch_key === propertyMapFetchKey(addr),
    [metadata.property_map_fetch_key],
  )

  const persistPatch = useCallback(
    async (patch: Record<string, string>) => {
      onMetadataPatch(patch)
      if (!claimId) return
      const merged: Record<string, string> = {}
      for (const [k, v] of Object.entries(metadata)) {
        if (typeof v === 'string') merged[k] = v
      }
      for (const [k, v] of Object.entries(patch)) {
        if (v === '') delete merged[k]
        else if (v !== undefined) merged[k] = v
      }
      await updateClaim(claimId, { property_metadata: merged }).catch(() => {
        /* persist is best-effort; local draft still has map metadata */
      })
    },
    [claimId, metadata, onMetadataPatch],
  )

  const fetchMap = useCallback(
    async (force = false) => {
      const addr = address.trim()
      if (addr.length < MIN_ADDRESS_LEN) return

      const fetchKey = metadata.property_map_fetch_key ?? ''
      const imagesDead = fetchKey !== '' && deadImageKeysRef.current.has(fetchKey)

      if (!force && isMapCurrent(addr) && metadata.property_map_satellite_path) {
        const prev = previewRef.current
        const sameKey = prev?.fetch_key === fetchKey
        // Keep existing data-URL previews; never wipe them just because paths exist.
        const satellitePreview = sameKey && prev?.satellite_preview ? prev.satellite_preview : ''
        const roadmapPreview = sameKey && prev?.roadmap_preview ? prev.roadmap_preview : ''
        const attachUrls = !imagesDead && !!claimId
        setPreview({
          resolved_address: metadata.property_map_resolved_address ?? '',
          latitude: metadata.property_latitude ? Number(metadata.property_latitude) : null,
          longitude: metadata.property_longitude ? Number(metadata.property_longitude) : null,
          fetch_key: fetchKey,
          satellite_url: attachUrls
            ? `/report-writer/claims/${claimId}/property-map/image?variant=satellite`
            : null,
          roadmap_url: attachUrls
            ? `/report-writer/claims/${claimId}/property-map/image?variant=roadmap`
            : null,
          satellite_preview: satellitePreview,
          roadmap_preview: roadmapPreview,
          attribution: ['Map data © Google'],
        })
        if (imagesDead && !satellitePreview && !roadmapPreview) {
          setError('Property map images unavailable. Use Refresh to re-fetch.')
        }
        return
      }

      const reqId = ++requestIdRef.current
      setLoading(true)
      setError(null)

      try {
        const response = await fetchPropertyMap(addr, claimId ?? undefined)
        if (reqId !== requestIdRef.current) return

        // Successful force/network fetch: clear dead-key for this fetch_key.
        if (response.fetch_key) {
          deadImageKeysRef.current.delete(response.fetch_key)
        }
        setPreview(response)
        if (claimId) {
          const patch = basePatchFromResponse(response)
          await persistPatch(patch)
        }
      } catch (err) {
        if (reqId !== requestIdRef.current) return
        setError(err instanceof Error ? err.message : 'Property map fetch failed')
      } finally {
        if (reqId === requestIdRef.current) {
          setLoading(false)
        }
      }
    },
    [address, claimId, isMapCurrent, metadata, persistPatch],
  )

  const refresh = useCallback(() => {
    void fetchMap(true)
  }, [fetchMap])

  /** After image endpoint 404s for this fetch_key, stop attaching URLs (no retry storm). */
  const markCachedImagesUnavailable = useCallback(() => {
    const key = previewRef.current?.fetch_key
    if (!key) return
    deadImageKeysRef.current.add(key)
    setPreview(prev =>
      prev
        ? {
            ...prev,
            satellite_url: null,
            roadmap_url: null,
          }
        : prev,
    )
    setError('Property map images unavailable. Use Refresh to re-fetch.')
  }, [])

  useEffect(() => {
    if (prevAddressRef.current !== address) {
      prevAddressRef.current = address
      if (metadata.property_map_fetch_key && !isMapCurrent(address.trim())) {
        onPropertyMapClear?.()
        setPreview(null)
        setError(null)
      }
    }
  }, [address, isMapCurrent, metadata.property_map_fetch_key, onPropertyMapClear])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const addr = address.trim()
    if (addr.length < MIN_ADDRESS_LEN) {
      setError(null)
      return
    }

    if (isMapCurrent(addr) && metadata.property_map_satellite_path) {
      void fetchMap(false)
      return
    }

    debounceRef.current = setTimeout(() => {
      void fetchMap(false)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [address, claimId, fetchMap, isMapCurrent, metadata.property_map_satellite_path])

  return {
    loading,
    error,
    refresh,
    preview,
    hasPersistedMaps: !!metadata.property_map_satellite_path,
    markCachedImagesUnavailable,
  }
}
