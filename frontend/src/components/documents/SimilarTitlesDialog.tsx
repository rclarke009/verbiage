import type { CSSProperties } from 'react'

import { formatSimilarityScore } from '../../lib/similarTitles'

import type { SimilarTitleWarning } from '../../lib/similarTitles'

interface Props {
  warnings: SimilarTitleWarning[]
  onConfirm: () => void
  onCancel: () => void
}

const overlayStyle: CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.55)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: 24,
}

const panelStyle: CSSProperties = {
  background: 'var(--app-bg)',
  borderRadius: 8,
  width: 'min(560px, 95vw)',
  maxHeight: 'min(80vh, 640px)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  border: '1px solid var(--app-border)',
}

const btnStyle: CSSProperties = {
  border: '1px solid var(--app-border)',
  borderRadius: 6,
  padding: '8px 14px',
  fontSize: 13,
  cursor: 'pointer',
  background: 'var(--app-surface)',
  color: 'var(--app-text)',
}

export function SimilarTitlesDialog({ warnings, onConfirm, onCancel }: Props) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="similar-titles-title"
      style={overlayStyle}
      onClick={onCancel}
    >
      <div style={panelStyle} onClick={e => e.stopPropagation()}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--app-border)' }}>
          <h3 id="similar-titles-title" style={{ margin: 0, fontSize: 15, color: 'var(--app-warning)' }}>
            Similar reports already in the library
          </h3>
          <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--app-text-muted)', lineHeight: 1.5 }}>
            The following look like reports you may already have indexed. Ingest anyway?
          </p>
        </div>

        <div style={{ padding: '12px 16px', overflow: 'auto', flex: 1 }}>
          {warnings.map(w => (
            <div key={w.proposed} style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{w.label}</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--app-text-muted)' }}>
                {w.matches.map(m => (
                  <li key={`${w.proposed}-${m.doc_id}`} style={{ marginBottom: 4 }}>
                    <span style={{ color: 'var(--app-text)' }}>{m.title || m.doc_id}</span>
                    {' · '}
                    {formatSimilarityScore(m.score)} match
                    {m.title && m.doc_id !== m.title ? (
                      <span style={{ color: 'var(--app-text-subtle)' }}> ({m.doc_id})</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 8,
            padding: '12px 16px',
            borderTop: '1px solid var(--app-border)',
          }}
        >
          <button type="button" onClick={onCancel} style={btnStyle}>
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              ...btnStyle,
              background: 'var(--app-warning-bg)',
              borderColor: 'var(--app-warning-border)',
              color: 'var(--app-warning)',
              fontWeight: 600,
            }}
          >
            Ingest anyway
          </button>
        </div>
      </div>
    </div>
  )
}
