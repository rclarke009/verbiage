import { useState, useCallback, useEffect, useRef } from 'react'
import type { LookupResult, RetrievalDebug, Source } from '../types'

import { apiOrigin, getAuthFetchInit } from '../lib/api'

const RESULTS_STORAGE_KEY = 'verbiage-search-results'
const LEGACY_RESULTS_STORAGE_KEY = 'verbiage-search-results'

function resultsStorageKey(userId: string | null): string {
  return userId ? `${RESULTS_STORAGE_KEY}:${userId}` : `${RESULTS_STORAGE_KEY}:guest`
}

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function parseRetrievalDebug(raw: unknown): RetrievalDebug | null {
  if (!raw || typeof raw !== 'object') return null
  const d = raw as Record<string, unknown>
  if (typeof d.rewritten_query !== 'string' || typeof d.original_query !== 'string') {
    return null
  }
  return {
    retried: d.retried !== false,
    original_query: d.original_query,
    rewritten_query: d.rewritten_query,
  }
}

function loadStoredResults(storageKey: string): LookupResult[] {
  if (typeof window === 'undefined') return []
  try {
    const raw =
      window.localStorage.getItem(storageKey) ??
      (storageKey.endsWith(':guest')
        ? window.localStorage.getItem(LEGACY_RESULTS_STORAGE_KEY)
        : null)
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

// Abort the stream if no bytes arrive for this long. The backend can die mid-stream
// (e.g. an OOM-killed worker); Render's proxy may hold the connection open, so the
// reader would otherwise hang forever with no error and the UI would spin indefinitely.
const STREAM_STALL_TIMEOUT_MS = 60000

/**
 * Stateless report search. Each call to `search` is an independent lookup — no
 * conversation history is sent to the backend (it embeds only the query). Results
 * are kept newest-first so the UI reads as a stack of lookups, not a dialogue.
 */
export function useReportSearch(
  topK = 3,
  retrievalMode: RetrievalMode = 'auto',
  userId: string | null = null,
) {
  const storageKey = resultsStorageKey(userId)
  const [results, setResults] = useState<LookupResult[]>(() => loadStoredResults(storageKey))
  const [searching, setSearching] = useState(false)
  const persistReady = useRef(false)

  useEffect(() => {
    persistReady.current = false
    setResults(loadStoredResults(storageKey))
  }, [storageKey])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!persistReady.current) {
      persistReady.current = true
      return
    }
    window.localStorage.setItem(storageKey, JSON.stringify(results))
    if (userId) {
      window.localStorage.removeItem(LEGACY_RESULTS_STORAGE_KEY)
      window.localStorage.removeItem(`${RESULTS_STORAGE_KEY}:guest`)
    }
  }, [results, storageKey, userId])

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
      const controller = new AbortController()
      const init = await getAuthFetchInit({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: query,
          top_k: topK,
          retrieval_mode: retrievalMode,
        }),
        signal: controller.signal,
      })

      let streamError: string | null = null
      // Watchdog: reset on every byte received. If it fires, the stream has stalled
      // (server likely died mid-response) and we abort so the reader stops hanging.
      let stalled = false
      let stallTimer: ReturnType<typeof setTimeout> | undefined
      const armStallTimer = () => {
        if (stallTimer) clearTimeout(stallTimer)
        stallTimer = setTimeout(() => {
          stalled = true
          controller.abort()
        }, STREAM_STALL_TIMEOUT_MS)
      }
      const clearStallTimer = () => {
        if (stallTimer) clearTimeout(stallTimer)
        stallTimer = undefined
      }

      try {
        armStallTimer()
        const response = await fetch(urlForFetch, init)
        if (!response.ok) {
          const t = (await response.text()).trim()
          // statusText is empty over HTTP/2, so always fall back to the status code
          // to avoid surfacing a bare "Error:" with no detail.
          throw new Error(t || response.statusText || `HTTP ${response.status}`)
        }
        if (!response.body) throw new Error('No response body')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        // Track the event type across read() chunks; an SSE frame can be split
        // across network reads, and is terminated by a blank line.
        let currentEvent = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          armStallTimer()
          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (line === '') {
              currentEvent = ''
              continue
            }
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim()
              try {
                const data = JSON.parse(dataStr) as Record<string, unknown>
                if (currentEvent === 'token' && typeof data.token === 'string') {
                  patch(r => ({ ...r, answer: r.answer + data.token }))
                } else if (currentEvent === 'sources') {
                  const corpusRaw = data.corpus
                  const corpus =
                    corpusRaw === 'demo' || corpusRaw === 'live' ? corpusRaw : null
                  patch(r => ({
                    ...r,
                    sources: Array.isArray(data.sources) ? (data.sources as Source[]) : r.sources,
                    chunksUsed:
                      typeof data.chunks_used === 'number' ? data.chunks_used : r.chunksUsed,
                    retrievalDebug: parseRetrievalDebug(data.retrieval_debug),
                    corpus,
                  }))
                } else if (currentEvent === 'error') {
                  const detail = typeof data.detail === 'string' ? data.detail : ''
                  streamError =
                    detail === 'retrieval_failed'
                      ? 'Search failed while retrieving from the report library. Please try again.'
                      : detail || 'The server reported an error while searching.'
                }
              } catch {
                /* ignore malformed SSE lines */
              }
            }
          }
        }
      } catch (err) {
        if (stalled) {
          streamError =
            'The server stopped responding. It may have timed out or restarted mid-request. Please try again.'
        } else {
          const msg = err instanceof Error && err.message ? err.message : ''
          streamError = msg || 'Something went wrong while contacting the server.'
        }
      } finally {
        clearStallTimer()
        if (streamError) {
          patch(r => ({ ...r, answer: r.answer ? r.answer : `Error: ${streamError}` }))
        }
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
      window.localStorage.removeItem(storageKey)
      if (userId) {
        window.localStorage.removeItem(LEGACY_RESULTS_STORAGE_KEY)
        window.localStorage.removeItem(`${RESULTS_STORAGE_KEY}:guest`)
      }
    }
  }, [storageKey, userId])

  return { results, searching, search, removeResult, clearResults }
}
