import type { Message } from '../../types'
import { SourceList } from './SourceList'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 12,
    }}>
      <div style={{
        maxWidth: '80%',
        background: isUser ? '#1976D2' : '#f5f5f5',
        color: isUser ? '#fff' : '#111',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        padding: '10px 14px',
        fontSize: 14,
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
      }}>
        {message.content}
        {!isUser && message.sources && (
          <SourceList sources={message.sources} chunksUsed={message.chunks_used} />
        )}
      </div>
    </div>
  )
}
