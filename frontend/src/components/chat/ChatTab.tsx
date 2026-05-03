import { useRef, useEffect } from 'react'
import { useStreamingAsk } from '../../hooks/useStreamingAsk'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'

export function ChatTab() {
  const { messages, streaming, ask, clearMessages } = useStreamingAsk()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 140px)' }}>
      {messages.length === 0 && (
        <div style={{ color: '#888', textAlign: 'center', marginTop: 40, fontSize: 14 }}>
          <p>Ask anything about your ingested engineering reports.</p>
          <p style={{ fontSize: 12 }}>Answers are grounded in retrieved document passages.</p>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
        {messages.map((msg, i) => <MessageBubble key={i} message={msg} />)}
        {streaming && messages[messages.length - 1]?.role === 'assistant' && messages[messages.length - 1].content === '' && (
          <div style={{ color: '#888', fontSize: 13, padding: '4px 0' }}>Searching reports…</div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length > 0 && (
        <button
          onClick={clearMessages}
          style={{ alignSelf: 'flex-start', background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 12, padding: '4px 0' }}
        >
          Clear conversation
        </button>
      )}

      <ChatInput onSubmit={ask} disabled={streaming} />
    </div>
  )
}
