import { useState, useCallback, useEffect } from 'react'
import type { Message, Source } from '../types'

const CHAT_STORAGE_KEY = 'true-ai-chat-messages'

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

export function useStreamingAsk() {
  const [messages, setMessages] = useState<Message[]>(loadStoredMessages)
  const [streaming, setStreaming] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  const ask = useCallback(async (question: string) => {
    if (streaming) return

    setStreaming(true)
    setMessages(prev => [...prev, { role: 'user', content: question }])
    // Placeholder assistant message to stream into
    setMessages(prev => [...prev, { role: 'assistant', content: '', sources: [], chunks_used: 0 }])

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

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

        // Process complete SSE lines
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        let currentEvent = ''
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim()
            try {
              const data = JSON.parse(dataStr)
              if (currentEvent === 'token' && data.token) {
                updateLastMessage(msg => ({ ...msg, content: msg.content + data.token }))
              } else if (currentEvent === 'sources') {
                updateLastMessage(msg => ({
                  ...msg,
                  sources: data.sources as Source[],
                  chunks_used: data.chunks_used as number,
                }))
              }
            } catch {
              // ignore parse errors on incomplete lines
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
  }, [streaming])

  const clearMessages = useCallback(() => {
    setMessages([])
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(CHAT_STORAGE_KEY)
    }
  }, [])

  return { messages, streaming, ask, clearMessages }
}
