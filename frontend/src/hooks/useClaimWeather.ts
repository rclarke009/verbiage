import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchClaimWeather, updateClaim } from '../api/reportWriter'
import type { ClaimPropertyMetadata, WeatherOptionsResponse } from '../types'
import { buildSelectionPatch } from '../components/report-writer/WeatherPicker'

const DEBOUNCE_MS = 600
const MIN_ADDRESS_LEN = 10

const WEATHER_META_KEYS = [
  'wind_speed_mph',
  'wind_gust_mph',
  'hail_size_in',
  'weather_stations',
  'weather_resolved_address',
  'weather_date_iso',
  'weather_source',
  'weather_fetched_at',
  'weather_fetch_key',
  'weather_wind_speed_source',
  'weather_wind_gust_source',
  'weather_hail_source',
  'weather_custom_wind_speed',
  'weather_custom_wind_gust',
  'weather_custom_hail',
  'weather_candidates_json',
] as const

function normalizeAddress(address: string): string {
  return address.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function weatherFetchKey(address: string, dateIso: string): string {
  return `${normalizeAddress(address)}|${dateIso}`
}

function basePatchFromOptions(
  options: WeatherOptionsResponse,
  address: string,
): Record<string, string> {
  const selectionPatch = buildSelectionPatch(options, options.selected, {})
  return {
    weather_source: options.source,
    weather_date_iso: options.date_iso,
    weather_fetched_at: new Date().toISOString(),
    weather_fetch_key: options.fetch_key || weatherFetchKey(address, options.date_iso),
    weather_candidates_json: JSON.stringify(options.candidates),
    ...selectionPatch,
    ...(options.stations.length > 0 ? { weather_stations: options.stations.join(', ') } : {}),
    ...(options.resolved_address ? { weather_resolved_address: options.resolved_address } : {}),
  }
}

export function clearWeatherMetadata(meta: ClaimPropertyMetadata): ClaimPropertyMetadata {
  const next = { ...meta }
  for (const key of WEATHER_META_KEYS) {
    delete next[key]
  }
  return next
}

function parseCachedOptions(meta: ClaimPropertyMetadata): WeatherOptionsResponse | null {
  const raw = meta.weather_candidates_json
  if (!raw) return null
  try {
    const candidates = JSON.parse(raw)
    if (!Array.isArray(candidates)) return null
    return {
      wind_speed_mph: meta.wind_speed_mph ? Number(meta.wind_speed_mph) : null,
      wind_gust_mph: meta.wind_gust_mph ? Number(meta.wind_gust_mph) : null,
      hail_size_in: meta.hail_size_in ? Number(meta.hail_size_in) : null,
      precip_in: null,
      stations: meta.weather_stations?.split(',').map(s => s.trim()).filter(Boolean) ?? [],
      resolved_address: meta.weather_resolved_address ?? '',
      latitude: null,
      longitude: null,
      date_iso: meta.weather_date_iso ?? '',
      date_display: meta.storm_date ?? meta.weather_date_iso ?? '',
      source: meta.weather_source ?? 'multi',
      fetch_key: meta.weather_fetch_key ?? '',
      candidates,
      selected: {
        ...(meta.weather_wind_speed_source && meta.weather_wind_speed_source !== 'custom'
          ? { wind_speed: meta.weather_wind_speed_source }
          : {}),
        ...(meta.weather_wind_gust_source && meta.weather_wind_gust_source !== 'custom'
          ? { wind_gust: meta.weather_wind_gust_source }
          : {}),
        ...(meta.weather_hail_source && meta.weather_hail_source !== 'custom'
          ? { hail_size: meta.weather_hail_source }
          : {}),
      },
      attribution: [],
    }
  } catch {
    return null
  }
}

export function useClaimWeather({
  claimId,
  address,
  stormDate,
  stormDateIso,
  metadata,
  onMetadataPatch,
  onWeatherClear,
}: {
  claimId: string | null
  address: string
  stormDate: string
  stormDateIso: string
  metadata: ClaimPropertyMetadata
  onMetadataPatch: (patch: Record<string, string>) => void
  onWeatherClear?: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [options, setOptions] = useState<WeatherOptionsResponse | null>(() => parseCachedOptions(metadata))
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)
  const prevStormKeyRef = useRef(`${stormDate}|${stormDateIso}`)

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

  const persistPatch = useCallback(
    async (patch: Record<string, string>) => {
      onMetadataPatch(patch)
      if (!claimId) return
      const merged: Record<string, string> = {}
      for (const [k, v] of Object.entries(metadata)) {
        if (typeof v === 'string') merged[k] = v
      }
      for (const [k, v] of Object.entries(patch)) {
        if (v === '') {
          delete merged[k]
        } else if (v !== undefined) {
          merged[k] = v
        }
      }
      await updateClaim(claimId, { property_metadata: merged }).catch(() => {
        /* persist is best-effort; local draft still has weather */
      })
    },
    [claimId, metadata, onMetadataPatch],
  )

  const fetchWeather = useCallback(
    async (force = false) => {
      const addr = address.trim()
      if (addr.length < MIN_ADDRESS_LEN || !dateForApi) return

      if (!force && isWeatherCurrent(addr)) {
        const cached = parseCachedOptions(metadata)
        if (cached) setOptions(cached)
        return
      }

      const reqId = ++requestIdRef.current
      setLoading(true)
      setError(null)

      try {
        const response = await fetchClaimWeather(addr, dateForApi)
        if (reqId !== requestIdRef.current) return

        setOptions(response)
        const patch = basePatchFromOptions(response, addr)
        await persistPatch(patch)
      } catch (err) {
        if (reqId !== requestIdRef.current) return
        setError(err instanceof Error ? err.message : 'Weather fetch failed')
      } finally {
        if (reqId === requestIdRef.current) {
          setLoading(false)
        }
      }
    },
    [address, dateForApi, isWeatherCurrent, metadata, persistPatch],
  )

  const refresh = useCallback(() => {
    void fetchWeather(true)
  }, [fetchWeather])

  const applySelectionPatch = useCallback(
    (patch: Record<string, string>) => {
      void persistPatch(patch)
    },
    [persistPatch],
  )

  // Clear stale weather when storm date changes
  useEffect(() => {
    const stormKey = `${stormDate}|${stormDateIso}`
    if (prevStormKeyRef.current !== stormKey) {
      prevStormKeyRef.current = stormKey
      if (metadata.weather_fetch_key) {
        onWeatherClear?.()
        setOptions(null)
      }
    }
  }, [stormDate, stormDateIso, metadata.weather_fetch_key, onWeatherClear])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const addr = address.trim()
    if (addr.length < MIN_ADDRESS_LEN || !dateForApi) {
      setError(null)
      return
    }

    if (isWeatherCurrent(addr)) {
      const cached = parseCachedOptions(metadata)
      if (cached) setOptions(cached)
      return
    }

    debounceRef.current = setTimeout(() => {
      void fetchWeather(false)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [address, dateForApi, fetchWeather, isWeatherCurrent, metadata])

  return { loading, error, refresh, options, applySelectionPatch }
}
