import { useRef, useState } from 'react'
import type { LookupResult, Source } from '../../types'
import { SourceList } from './SourceList'

interface Props {
  result: LookupResult
  onSave: (text: string, query: string, sources: Source[]) => void
  onRemove: (id: string) => void
}

/** Returns the user's current selection if it falls inside `container`, else ''. */
function selectionWithin(container: HTMLElement | null): string {
  if (!container || typeof window === 'undefined') return ''
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return ''
  const range = sel.getRangeAt(0)
  if (!container.contains(range.commonAncestorContainer)) return ''
  return sel.toString().trim()
}

export function ResultCard({ result, onSave, onRemove }: Props) {
  const answerRef = useRef<HTMLDivElement>(null)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    const selected = selectionWithin(answerRef.current)
    const text = selected || result.answer
    if (!text.trim()) return
    onSave(text, result.query, result.sources)
    setSaved(true)
    window.setTimeout(() => setSaved(false), 1500)
  }

  return (
    <div
      style={{
        border: '1px solid var(--app-border)',
        borderRadius: 10,
        padding: '14px 16px',
        marginBottom: 14,
        background: 'var(--app-bg)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--app-primary)', marginBottom: 8 }}>
          {result.query}
        </div>
        <button
          type="button"
          onClick={() => onRemove(result.id)}
          title="Remove this result"
          style={{ background: 'none', border: 'none', color: 'var(--app-text-subtle)', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: 0 }}
        >
          ×
        </button>
      </div>

      <div
        ref={answerRef}
        style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--app-text)', whiteSpace: 'pre-wrap' }}
      >
        {result.answer}
        {result.streaming && !result.answer && (
          <span style={{ color: 'var(--app-text-subtle)' }}>Searching reports…</span>
        )}
      </div>

      {result.sources.length > 0 && (
        <SourceList sources={result.sources} chunksUsed={result.chunksUsed} />
      )}

      {!result.streaming && result.answer && (
        <div style={{ marginTop: 10 }}>
          <button
            type="button"
            onClick={handleSave}
            style={{
              background: saved ? 'var(--app-success-bg)' : 'var(--app-info-bg)',
              border: '1px solid',
              borderColor: saved ? 'var(--app-success-border)' : 'var(--app-info-border)',
              borderRadius: 6,
              padding: '4px 12px',
              cursor: 'pointer',
              fontSize: 12,
              color: saved ? 'var(--app-success)' : 'var(--app-primary)',
              fontWeight: 600,
            }}
          >
            {saved ? '✓ Saved' : '＋ Save to collection'}
          </button>
          <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--app-text-subtle)' }}>
            Tip: highlight text first to save just that passage.
          </span>
        </div>
      )}
    </div>
  )
}
