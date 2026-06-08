import { useCallback, useState } from 'react'
import type { GenerationSectionState, GenerationState, ReportWriterSource } from '../types'
import { apiOrigin, getAuthFetchInit } from '../lib/api'

const STREAM_STALL_TIMEOUT_MS = 60000

function emptySections(sectionKeys: string[]): Record<string, GenerationSectionState> {
  return Object.fromEntries(
    sectionKeys.map(k => [k, { content: '', streaming: false, sources: [] }]),
  )
}

const initialState: GenerationState = {
  runId: null,
  claimId: null,
  activeNode: null,
  status: 'idle',
  refusalReason: null,
  retrievedSources: [],
  sections: {},
  error: null,
}

function mapChunkSources(chunks: Record<string, unknown>[]): ReportWriterSource[] {
  return chunks.map(c => ({
    chunk_id: String(c.chunk_id ?? ''),
    doc_id: String(c.doc_id ?? ''),
    score: typeof c.score === 'number' ? c.score : undefined,
    snippet: String(c.content_snippet ?? c.snippet ?? ''),
    document_title: (c.document_title as string) ?? null,
    source_url: (c.source_url as string) ?? null,
  }))
}

export function useReportWriterStream() {
  const [state, setState] = useState<GenerationState>(initialState)
  const [generating, setGenerating] = useState(false)

  const reset = useCallback(() => {
    setState(initialState)
  }, [])

  const generate = useCallback(async (
    claimId: string,
    url: string,
    body?: object,
    sectionKeys: string[] = [],
  ) => {
    if (generating) return
    setGenerating(true)
    setState({
      ...initialState,
      claimId,
      status: 'running',
      sections: emptySections(sectionKeys),
    })

    const controller = new AbortController()
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
    }

    const patch = (updater: (s: GenerationState) => GenerationState) => {
      setState(prev => updater(prev))
    }

    try {
      const init = await getAuthFetchInit({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : '{}',
        signal: controller.signal,
      })
      armStallTimer()
      const response = await fetch(`${apiOrigin()}${url}`, init)
      if (!response.ok) {
        throw new Error(await response.text())
      }
      if (!response.body) throw new Error('No response body')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
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
              if (currentEvent === 'run_started') {
                patch(s => ({ ...s, runId: String(data.run_id ?? '') }))
              } else if (currentEvent === 'sources') {
                const chunks = Array.isArray(data.chunks) ? data.chunks : []
                patch(s => ({ ...s, retrievedSources: mapChunkSources(chunks as Record<string, unknown>[]) }))
              } else if (currentEvent === 'node_update') {
                const node = typeof data.node === 'string' ? data.node : null
                patch(s => ({ ...s, activeNode: node }))
              } else if (currentEvent === 'section_start') {
                const key = String(data.section_key ?? '')
                patch(s => ({
                  ...s,
                  sections: {
                    ...s.sections,
                    [key]: { ...(s.sections[key] ?? { content: '', sources: [] }), streaming: true, content: '' },
                  },
                }))
              } else if (currentEvent === 'section_delta') {
                const key = String(data.section_key ?? '')
                const delta = String(data.delta ?? '')
                patch(s => ({
                  ...s,
                  sections: {
                    ...s.sections,
                    [key]: {
                      ...(s.sections[key] ?? { streaming: false, sources: [] }),
                      content: (s.sections[key]?.content ?? '') + delta,
                    },
                  },
                }))
              } else if (currentEvent === 'section_complete') {
                const key = String(data.section_key ?? '')
                const sources = Array.isArray(data.sources) ? mapChunkSources(data.sources as Record<string, unknown>[]) : []
                patch(s => ({
                  ...s,
                  sections: {
                    ...s.sections,
                    [key]: {
                      content: String(data.content ?? s.sections[key]?.content ?? ''),
                      streaming: false,
                      sources,
                    },
                  },
                }))
              } else if (currentEvent === 'refused') {
                patch(s => ({
                  ...s,
                  status: 'refused',
                  refusalReason: String(data.reason ?? ''),
                }))
              } else if (currentEvent === 'run_complete') {
                const st = String(data.status ?? 'completed')
                patch(s => ({
                  ...s,
                  status: st === 'refused' ? 'refused' : 'complete',
                }))
              } else if (currentEvent === 'error') {
                patch(s => ({
                  ...s,
                  status: 'error',
                  error: String(data.detail ?? 'Generation failed'),
                }))
              }
            } catch {
              /* ignore malformed SSE */
            }
          }
        }
      }
    } catch (err) {
      if (stalled) {
        patch(s => ({ ...s, status: 'error', error: 'Server stopped responding mid-generation.' }))
      } else {
        const msg = err instanceof Error ? err.message : 'Generation failed'
        patch(s => ({ ...s, status: 'error', error: msg }))
      }
    } finally {
      clearStallTimer()
      setGenerating(false)
    }
  }, [generating])

  return { state, generating, generate, reset }
}
