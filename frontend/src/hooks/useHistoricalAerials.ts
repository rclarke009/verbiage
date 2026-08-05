import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchHistoricalAerials, updateClaim } from '../api/reportWriter'
import type {
  ClaimPropertyMetadata,
  HistoricalAerialItem,
  HistoricalAerialsResponse,
} from '../types'

const DEBOUNCE_MS = 600
const MIN_ADDRESS_LEN = 10

const HISTORICAL_AERIALS_META_KEYS = [
  'historical_aerials_fetch_key',
  'historical_aerials_fetched_at',
  'historical_aerials_comment',
  'historical_aerials',
  'historical_aerials_resolved_address',
  'historical_aerials_latitude',
  'historical_aerials_longitude',
  'historical_aerials_dol_year',
] as const

function normalizeAddress(address: string): string {
  return address.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function historicalAerialsFetchKey(address: string, dolYear: number): string {
  return `${normalizeAddress(address)}|${dolYear}`
}

function dolYearFromMeta(stormDateIso: string, stormDate: string): number | null {
  const iso = stormDateIso.trim()
  if (/^\d{4}-\d{2}-\d{2}/.test(iso)) return Number(iso.slice(0, 4))
  const display = stormDate.trim()
  const yearMatch = display.match(/\b(19|20)\d{2}\b/)
  if (yearMatch) return Number(yearMatch[0])
  return null
}

function stormDateForFetch(stormDateIso: string, stormDate: string): string {
  return stormDateIso.trim() || stormDate.trim()
}

type MetaPatch = Record<string, string | HistoricalAerialItem[] | undefined>

export function clearHistoricalAerialsMetadata(meta: ClaimPropertyMetadata): ClaimPropertyMetadata {
  const next = { ...meta }
  for (const key of HISTORICAL_AERIALS_META_KEYS) {
    delete next[key]
  }
  return next
}

function aerialsFromMetadata(
  claimId: string | null,
  metadata: ClaimPropertyMetadata,
  prev: HistoricalAerialsResponse | null,
): HistoricalAerialsResponse | null {
  const list = Array.isArray(metadata.historical_aerials) ? metadata.historical_aerials : []
  if (!list.length || !metadata.historical_aerials_fetch_key) return null
  const dolYear = Number(metadata.historical_aerials_dol_year || 0)
  return {
    resolved_address: metadata.historical_aerials_resolved_address ?? '',
    latitude: metadata.historical_aerials_latitude
      ? Number(metadata.historical_aerials_latitude)
      : null,
    longitude: metadata.historical_aerials_longitude
      ? Number(metadata.historical_aerials_longitude)
      : null,
    fetch_key: metadata.historical_aerials_fetch_key,
    dol_year: dolYear,
    comment: metadata.historical_aerials_comment ?? '',
    attribution: ['NAIP / USGS The National Map / USDA'],
    aerials: list.map(item => {
      const prevItem = prev?.aerials.find(a => a.year === item.year)
      return {
        year: item.year,
        path: item.path,
        include: !!item.include,
        preview: prevItem?.preview ?? '',
        image_url:
          claimId && item.path
            ? `/report-writer/claims/${claimId}/historical-aerials/image?year=${item.year}`
            : null,
      }
    }),
  }
}

export function useHistoricalAerials({
  claimId,
  address,
  stormDate,
  stormDateIso,
  metadata,
  onMetadataPatch,
  onHistoricalAerialsClear,
}: {
  claimId: string | null
  address: string
  stormDate: string
  stormDateIso: string
  metadata: ClaimPropertyMetadata
  onMetadataPatch: (patch: MetaPatch) => void
  onHistoricalAerialsClear?: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<HistoricalAerialsResponse | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)
  const prevKeyRef = useRef<string>('')
  const deadImageKeysRef = useRef<Set<string>>(new Set())
  const previewRef = useRef(preview)
  previewRef.current = preview

  const dolYear = dolYearFromMeta(stormDateIso, stormDate)
  const dateParam = stormDateForFetch(stormDateIso, stormDate)

  const isCurrent = useCallback(
    (addr: string, year: number | null) => {
      if (year == null) return false
      return metadata.historical_aerials_fetch_key === historicalAerialsFetchKey(addr, year)
    },
    [metadata.historical_aerials_fetch_key],
  )

  const persistPatch = useCallback(
    async (patch: MetaPatch) => {
      onMetadataPatch(patch)
      if (!claimId) return
      const merged: ClaimPropertyMetadata = { ...metadata }
      for (const [k, v] of Object.entries(patch)) {
        if (v === '' || v === undefined) delete merged[k]
        else merged[k] = v as ClaimPropertyMetadata[string]
      }
      await updateClaim(claimId, { property_metadata: merged }).catch(() => {
        /* persist is best-effort; local draft still has aerial metadata */
      })
    },
    [claimId, metadata, onMetadataPatch],
  )

  const fetchAerials = useCallback(
    async (force = false) => {
      const addr = address.trim()
      if (addr.length < MIN_ADDRESS_LEN || !dateParam || dolYear == null) return

      const fetchKey = metadata.historical_aerials_fetch_key ?? ''
      const imagesDead = fetchKey !== '' && deadImageKeysRef.current.has(fetchKey)
      const hasPersisted = Array.isArray(metadata.historical_aerials) && metadata.historical_aerials.length > 0

      if (!force && isCurrent(addr, dolYear) && hasPersisted) {
        const cached = aerialsFromMetadata(claimId, metadata, previewRef.current)
        if (cached) {
          if (imagesDead) {
            cached.aerials = cached.aerials.map(a => ({ ...a, image_url: null }))
            setError('Historical aerial images unavailable. Use Refresh to re-fetch.')
          }
          setPreview(cached)
        }
        return
      }

      const reqId = ++requestIdRef.current
      setLoading(true)
      setError(null)

      try {
        const response = await fetchHistoricalAerials(addr, dateParam, claimId ?? undefined)
        if (reqId !== requestIdRef.current) return
        if (response.fetch_key) {
          deadImageKeysRef.current.delete(response.fetch_key)
        }
        setPreview(response)
        if (claimId) {
          await persistPatch({
            historical_aerials_fetch_key: response.fetch_key,
            historical_aerials_fetched_at: new Date().toISOString(),
            historical_aerials_comment: response.comment || metadata.historical_aerials_comment || '',
            historical_aerials_resolved_address: response.resolved_address,
            historical_aerials_latitude:
              response.latitude != null ? String(response.latitude) : '',
            historical_aerials_longitude:
              response.longitude != null ? String(response.longitude) : '',
            historical_aerials_dol_year: String(response.dol_year),
            historical_aerials: response.aerials.map(a => ({
              year: a.year,
              path: a.path ?? null,
              include: !!a.include,
            })),
          })
        }
        if (!response.aerials.length) {
          setError('No NAIP coverage for this date range.')
        }
      } catch (err) {
        if (reqId !== requestIdRef.current) return
        setError(err instanceof Error ? err.message : 'Historical aerials fetch failed')
      } finally {
        if (reqId === requestIdRef.current) {
          setLoading(false)
        }
      }
    },
    [address, claimId, dateParam, dolYear, isCurrent, metadata, persistPatch],
  )

  const refresh = useCallback(() => {
    void fetchAerials(true)
  }, [fetchAerials])

  const setInclude = useCallback(
    (year: number, include: boolean) => {
      const list = Array.isArray(metadata.historical_aerials)
        ? metadata.historical_aerials.map(item =>
            item.year === year ? { ...item, include } : item,
          )
        : []
      setPreview(prev =>
        prev
          ? {
              ...prev,
              aerials: prev.aerials.map(a => (a.year === year ? { ...a, include } : a)),
            }
          : prev,
      )
      void persistPatch({ historical_aerials: list })
    },
    [metadata.historical_aerials, persistPatch],
  )

  const setComment = useCallback(
    (comment: string) => {
      setPreview(prev => (prev ? { ...prev, comment } : prev))
      void persistPatch({ historical_aerials_comment: comment })
    },
    [persistPatch],
  )

  const markCachedImagesUnavailable = useCallback(() => {
    const key = previewRef.current?.fetch_key
    if (!key) return
    deadImageKeysRef.current.add(key)
    setPreview(prev =>
      prev
        ? {
            ...prev,
            aerials: prev.aerials.map(a => ({ ...a, image_url: null })),
          }
        : prev,
    )
    setError('Historical aerial images unavailable. Use Refresh to re-fetch.')
  }, [])

  useEffect(() => {
    const key =
      dolYear != null ? historicalAerialsFetchKey(address.trim(), dolYear) : ''
    if (prevKeyRef.current && prevKeyRef.current !== key) {
      if (metadata.historical_aerials_fetch_key && !isCurrent(address.trim(), dolYear)) {
        onHistoricalAerialsClear?.()
        setPreview(null)
        setError(null)
      }
    }
    prevKeyRef.current = key
  }, [
    address,
    dolYear,
    isCurrent,
    metadata.historical_aerials_fetch_key,
    onHistoricalAerialsClear,
  ])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const addr = address.trim()
    if (addr.length < MIN_ADDRESS_LEN || !dateParam || dolYear == null) {
      setError(null)
      return
    }

    if (
      isCurrent(addr, dolYear) &&
      Array.isArray(metadata.historical_aerials) &&
      metadata.historical_aerials.length > 0
    ) {
      void fetchAerials(false)
      return
    }

    debounceRef.current = setTimeout(() => {
      void fetchAerials(false)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [
    address,
    claimId,
    dateParam,
    dolYear,
    fetchAerials,
    isCurrent,
    metadata.historical_aerials,
  ])

  return {
    loading,
    error,
    refresh,
    preview,
    setInclude,
    setComment,
    hasPersistedAerials: Array.isArray(metadata.historical_aerials) && metadata.historical_aerials.length > 0,
    markCachedImagesUnavailable,
  }
}
