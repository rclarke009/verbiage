import { useState, useCallback, useEffect } from 'react'
import type { LookupResult, Source } from '../types'

import { apiOrigin, getAuthFetchInit } from '../lib/api'

const RESULTS_STORAGE_KEY = 'verbiage-search-results'

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadStoredResults(): LookupResult[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(RESULTS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    // A result persisted mid-stream should not come back as "still streaming".
    return (parsed as LookupResult[]).map(r => ({ ...r, streaming: false }))
  } catch {
    return []
  }
}

type RetrievalMode = 'vector' | 'lexical' | 'hybrid' | 'auto'

/**
 * Stateless report search. Each call to `search` is an independent lookup — no
 * conversation history is sent to the backend (it embeds only the query). Results
 * are kept newest-first so the UI reads as a stack of lookups, not a dialogue.
 */
export function useReportSearch(topK = 5, retrievalMode: RetrievalMode = 'auto') {
  const [results, setResults] = useState<LookupResult[]>(loadStoredResults)
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(results))
  }, [results])

  const search = useCallback(
    async (query: string) => {
      if (searching) return

      const id = newId()
      setSearching(true)
      setResults(prev => [
        { id, query, answer: '', sources: [], chunksUsed: 0, streaming: true },
        ...prev,
      ])

      const patch = (updater: (r: LookupResult) => LookupResult) => {
        setResults(prev => prev.map(r => (r.id === id ? updater(r) : r)))
      }

      const urlForFetch = `${apiOrigin()}/ask/stream`
      const init = await getAuthFetchInit({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: query,
          top_k: topK,
          retrieval_mode: retrievalMode,
        }),
      })

      try {
        const response = await fetch(urlForFetch, init)
        if (!response.ok) {
          const t = await response.text()
          throw new Error(t || response.statusText)
        }
        if (!response.body) throw new Error('No response body')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          let currentEvent = ''
          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim()
              try {
                const data = JSON.parse(dataStr) as Record<string, unknown>
                if (currentEvent === 'token' && typeof data.token === 'string') {
                  patch(r => ({ ...r, answer: r.answer + data.token }))
                } else if (currentEvent === 'sources') {
                  patch(r => ({
                    ...r,
                    sources: Array.isArray(data.sources) ? (data.sources as Source[]) : r.sources,
                    chunksUsed:
                      typeof data.chunks_used === 'number' ? data.chunks_used : r.chunksUsed,
                  }))
                }
              } catch {
                /* ignore malformed SSE lines */
              }
            }
          }
        }
      } catch (err) {
        patch(r => ({
          ...r,
          answer: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        }))
      } finally {
        patch(r => ({ ...r, streaming: false }))
        setSearching(false)
      }
    },
    [searching, topK, retrievalMode],
  )

  const removeResult = useCallback((id: string) => {
    setResults(prev => prev.filter(r => r.id !== id))
  }, [])

  const clearResults = useCallback(() => {
    setResults([])
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(RESULTS_STORAGE_KEY)
    }
  }, [])

  return { results, searching, search, removeResult, clearResults }
}
