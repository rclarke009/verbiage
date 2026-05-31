import { useState, useCallback, useEffect } from 'react'
import type { SavedPassage, Source } from '../types'

const COLLECTED_STORAGE_KEY = 'verbiage-collected-passages'

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadStored(): SavedPassage[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(COLLECTED_STORAGE_KEY)
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
export function useCollectedPassages() {
  const [passages, setPassages] = useState<SavedPassage[]>(loadStored)

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(COLLECTED_STORAGE_KEY, JSON.stringify(passages))
  }, [passages])

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
      window.localStorage.removeItem(COLLECTED_STORAGE_KEY)
    }
  }, [])

  return { passages, savePassage, removePassage, clearPassages }
}
