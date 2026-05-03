import { useState, useCallback, useEffect } from 'react'
import type { Message, Source } from '../types'

import { apiOrigin, getAuthFetchInit } from '../lib/api'

const CHAT_STORAGE_KEY = 'verbiage-chat-messages'

function loadStoredMessages(): Message[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Message[]) : []
  } catch {
    return []
  }
}

export function useStreamingAsk(topK = 5) {
  const [messages, setMessages] = useState<Message[]>(loadStoredMessages)
  const [streaming, setStreaming] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  const ask = useCallback(
    async (question: string) => {
      if (streaming) return

      setStreaming(true)
      setMessages(prev => [...prev, { role: 'user', content: question }])
      setMessages(prev => [...prev, { role: 'assistant', content: '', sources: [], chunks_used: 0 }])

      const urlForFetch = `${apiOrigin()}/ask/stream`
      const init = await getAuthFetchInit({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          top_k: topK,
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

        const updateLastMessage = (updater: (msg: Message) => Message) => {
          setMessages(prev => {
            const next = [...prev]
            next[next.length - 1] = updater(next[next.length - 1])
            return next
          })
        }

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
                  updateLastMessage(msg => ({
                    ...msg,
                    content: msg.content + data.token,
                  }))
                } else if (currentEvent === 'sources') {
                  updateLastMessage(msg => ({
                    ...msg,
                    sources: Array.isArray(data.sources) ? (data.sources as Source[]) : [],
                    chunks_used:
                      typeof data.chunks_used === 'number' ? data.chunks_used : msg.chunks_used,
                  }))
                }
              } catch {
                /* ignore malformed SSE lines */
              }
            }
          }
        }
      } catch (err) {
        setMessages(prev => {
          const next = [...prev]
          next[next.length - 1] = {
            ...next[next.length - 1],
            content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
          }
          return next
        })
      } finally {
        setStreaming(false)
      }
    },
    [streaming, topK],
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(CHAT_STORAGE_KEY)
    }
  }, [])

  return { messages, streaming, ask, clearMessages }
}
