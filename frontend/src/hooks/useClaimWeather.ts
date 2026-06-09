import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchClaimWeather, updateClaim } from '../api/reportWriter'
import type { ClaimPropertyMetadata } from '../types'

const DEBOUNCE_MS = 600
const MIN_ADDRESS_LEN = 10

const WEATHER_META_KEYS = [
  'wind_speed_mph',
  'wind_gust_mph',
  'weather_stations',
  'weather_resolved_address',
  'weather_date_iso',
  'weather_source',
  'weather_fetched_at',
  'weather_fetch_key',
] as const

function normalizeAddress(address: string): string {
  return address.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function weatherFetchKey(address: string, dateIso: string): string {
  return `${normalizeAddress(address)}|${dateIso}`
}

function weatherPatchFromSnapshot(
  snapshot: Awaited<ReturnType<typeof fetchClaimWeather>>,
  address: string,
): Record<string, string> {
  const patch: Record<string, string> = {
    weather_source: snapshot.source,
    weather_date_iso: snapshot.date_iso,
    weather_fetched_at: new Date().toISOString(),
    weather_fetch_key: snapshot.fetch_key || weatherFetchKey(address, snapshot.date_iso),
  }
  if (snapshot.wind_speed_mph != null) {
    patch.wind_speed_mph = String(Math.round(snapshot.wind_speed_mph))
  }
  if (snapshot.wind_gust_mph != null) {
    patch.wind_gust_mph = String(Math.round(snapshot.wind_gust_mph))
  }
  if (snapshot.stations.length > 0) {
    patch.weather_stations = snapshot.stations.join(', ')
  }
  if (snapshot.resolved_address) {
    patch.weather_resolved_address = snapshot.resolved_address
  }
  return patch
}

export function clearWeatherMetadata(meta: ClaimPropertyMetadata): ClaimPropertyMetadata {
  const next = { ...meta }
  for (const key of WEATHER_META_KEYS) {
    delete next[key]
  }
  return next
}

export function useClaimWeather({
  claimId,
  address,
  stormDate,
  stormDateIso,
  metadata,
  onMetadataPatch,
}: {
  claimId: string | null
  address: string
  stormDate: string
  stormDateIso: string
  metadata: ClaimPropertyMetadata
  onMetadataPatch: (patch: Record<string, string>) => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)

  const dateForApi = stormDateIso || stormDate

  const isWeatherCurrent = useCallback(
    (addr: string) => {
      const dateKey = stormDateIso || metadata.weather_date_iso || ''
      if (!dateKey) return false
      return (
        metadata.weather_fetch_key === weatherFetchKey(addr, dateKey) &&
        metadata.storm_date === stormDate &&
        (stormDateIso ? metadata.storm_date_iso === stormDateIso : true)
      )
    },
    [metadata, stormDate, stormDateIso],
  )

  const fetchWeather = useCallback(
    async (force = false) => {
      const addr = address.trim()
      if (addr.length < MIN_ADDRESS_LEN || !dateForApi) return

      if (!force && isWeatherCurrent(addr)) return

      const reqId = ++requestIdRef.current
      setLoading(true)
      setError(null)

      try {
        const snapshot = await fetchClaimWeather(addr, dateForApi)
        if (reqId !== requestIdRef.current) return

        const patch = weatherPatchFromSnapshot(snapshot, addr)
        onMetadataPatch(patch)

        if (claimId) {
          const merged: Record<string, string> = {}
          for (const [k, v] of Object.entries({ ...metadata, ...patch })) {
            if (v !== undefined) merged[k] = v
          }
          await updateClaim(claimId, { property_metadata: merged }).catch(() => {
            /* persist is best-effort; local draft still has weather */
          })
        }
      } catch (err) {
        if (reqId !== requestIdRef.current) return
        setError(err instanceof Error ? err.message : 'Weather fetch failed')
      } finally {
        if (reqId === requestIdRef.current) {
          setLoading(false)
        }
      }
    },
    [address, claimId, dateForApi, isWeatherCurrent, metadata, onMetadataPatch],
  )

  const refresh = useCallback(() => {
    void fetchWeather(true)
  }, [fetchWeather])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const addr = address.trim()
    if (addr.length < MIN_ADDRESS_LEN || !dateForApi) {
      setError(null)
      return
    }

    if (isWeatherCurrent(addr)) return

    debounceRef.current = setTimeout(() => {
      void fetchWeather(false)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [address, dateForApi, fetchWeather, isWeatherCurrent])

  return { loading, error, refresh }
}
