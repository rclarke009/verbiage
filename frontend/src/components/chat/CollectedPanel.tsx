import { useState } from 'react'
import type { SavedPassage } from '../../types'

interface Props {
  passages: SavedPassage[]
  onRemove: (id: string) => void
  onClear: () => void
}

function attributionFor(p: SavedPassage): string {
  const names = p.sources.map(s => s.filename).filter(Boolean)
  if (!names.length) return ''
  const unique = Array.from(new Set(names))
  return unique.join('; ')
}

function buildClipboardText(passages: SavedPassage[]): string {
  return passages
    .map(p => {
      const attribution = attributionFor(p)
      return attribution ? `${p.text}\n— ${attribution}` : p.text
    })
    .join('\n\n')
}

export function CollectedPanel({ passages, onRemove, onClear }: Props) {
  const [copied, setCopied] = useState(false)

  const copyAll = async () => {
    if (!passages.length) return
    try {
      await navigator.clipboard.writeText(buildClipboardText(passages))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable (e.g. insecure context) — no-op */
    }
  }

  return (
    <aside
      style={{
        width: 300,
        flexShrink: 0,
        borderLeft: '1px solid var(--app-border)',
        paddingLeft: 16,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: 'var(--app-text)' }}>
          Collected passages ({passages.length})
        </h3>
      </div>
      <p style={{ fontSize: 11, color: 'var(--app-text-subtle)', margin: '0 0 10px' }}>
        Text you keep here builds up your new report draft. Each search is independent.
      </p>

      {passages.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
          <button
            type="button"
            onClick={copyAll}
            style={{
              background: copied ? 'var(--app-success-bg)' : 'var(--app-info-bg)',
              border: '1px solid', borderColor: copied ? 'var(--app-success-border)' : 'var(--app-info-border)',
              borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12,
              color: copied ? 'var(--app-success)' : 'var(--app-primary)', fontWeight: 600,
            }}
          >
            {copied ? '✓ Copied' : 'Copy all'}
          </button>
          <button
            type="button"
            onClick={onClear}
            style={{
              background: 'none', border: '1px solid var(--app-border)', borderRadius: 6,
              padding: '4px 10px', cursor: 'pointer', fontSize: 12, color: 'var(--app-text-subtle)',
            }}
          >
            Clear
          </button>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {passages.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--app-text-subtle)', marginTop: 8 }}>
            No saved passages yet. Use “Save to collection” on any result.
          </div>
        ) : (
          passages.map(p => {
            const attribution = attributionFor(p)
            return (
              <div
                key={p.id}
                style={{
                  border: '1px solid var(--app-border)', borderRadius: 8, padding: '8px 10px',
                  marginBottom: 8, background: 'var(--app-surface)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ fontSize: 11, color: 'var(--app-primary)', fontWeight: 600 }}>{p.query}</span>
                  <button
                    type="button"
                    onClick={() => onRemove(p.id)}
                    title="Remove"
                    style={{ background: 'none', border: 'none', color: 'var(--app-text-subtle)', cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: 0 }}
                  >
                    ×
                  </button>
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--app-text)', marginTop: 4, whiteSpace: 'pre-wrap' }}>
                  {p.text}
                </div>
                {attribution && (
                  <div style={{ fontSize: 11, color: 'var(--app-text-subtle)', marginTop: 6 }}>— {attribution}</div>
                )}
              </div>
            )
          })
        )}
      </div>
    </aside>
  )
}
