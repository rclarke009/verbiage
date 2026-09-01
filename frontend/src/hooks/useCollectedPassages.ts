import { useState, useCallback, useEffect, useRef } from 'react'
import type { SavedPassage, Source } from '../types'

const COLLECTED_STORAGE_KEY = 'verbiage-collected-passages'
const LEGACY_COLLECTED_STORAGE_KEY = 'verbiage-collected-passages'

function collectedStorageKey(userId: string | null): string {
  return userId ? `${COLLECTED_STORAGE_KEY}:${userId}` : `${COLLECTED_STORAGE_KEY}:guest`
}

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadStored(storageKey: string): SavedPassage[] {
  if (typeof window === 'undefined') return []
  try {
    const raw =
      window.localStorage.getItem(storageKey) ??
      (storageKey.endsWith(':guest')
        ? window.localStorage.getItem(LEGACY_COLLECTED_STORAGE_KEY)
        : null)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as SavedPassage[]) : []
  } catch {
    return []
  }
}

/**
 * The durable artifact of a search session: passages the user kept aside to reuse
 * while drafting a new report. Persisted to localStorage, independent of the
 * (stateless) search results themselves.
 */
export function useCollectedPassages(userId: string | null = null) {
  const storageKey = collectedStorageKey(userId)
  const [passages, setPassages] = useState<SavedPassage[]>(() => loadStored(storageKey))
  const persistReady = useRef(false)

  useEffect(() => {
    persistReady.current = false
    setPassages(loadStored(storageKey))
  }, [storageKey])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!persistReady.current) {
      persistReady.current = true
      return
    }
    window.localStorage.setItem(storageKey, JSON.stringify(passages))
    if (userId) {
      window.localStorage.removeItem(LEGACY_COLLECTED_STORAGE_KEY)
      window.localStorage.removeItem(`${COLLECTED_STORAGE_KEY}:guest`)
    }
  }, [passages, storageKey, userId])

  const savePassage = useCallback((text: string, query: string, sources: Source[]) => {
    const trimmed = text.trim()
    if (!trimmed) return
    setPassages(prev => {
      // De-dupe identical text so repeated saves don't stack up.
      if (prev.some(p => p.text === trimmed)) return prev
      return [
        ...prev,
        { id: newId(), text: trimmed, query, sources, savedAt: Date.now() },
      ]
    })
  }, [])

  const removePassage = useCallback((id: string) => {
    setPassages(prev => prev.filter(p => p.id !== id))
  }, [])

  const clearPassages = useCallback(() => {
    setPassages([])
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(storageKey)
      if (userId) {
        window.localStorage.removeItem(LEGACY_COLLECTED_STORAGE_KEY)
        window.localStorage.removeItem(`${COLLECTED_STORAGE_KEY}:guest`)
      }
    }
  }, [storageKey, userId])

  return { passages, savePassage, removePassage, clearPassages }
}
