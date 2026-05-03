import { useState } from 'react'
import type { Source } from '../../types'

interface Props {
  sources: Source[]
  chunksUsed?: number
}

export function SourceList({ sources, chunksUsed }: Props) {
  const [open, setOpen] = useState(false)
  if (!sources.length) return null

  const isDriveLike = (s: Source) =>
    (s.source_type === 'google_drive' || ((s.source || '').toLowerCase().includes('drive')))

  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: '1px solid #ccc',
          borderRadius: 4,
          padding: '4px 10px',
          cursor: 'pointer',
          fontSize: 12,
          color: '#555',
        }}
      >
        {open ? '▾' : '▸'} Sources ({sources.length})
        {chunksUsed !== undefined ? ` · ${chunksUsed} passages retrieved` : ''}
      </button>
      {open && (
        <div style={{ marginTop: 8, paddingLeft: 8, borderLeft: '3px solid #E3F2FD' }}>
          {sources.map((src, i) => {
            const parts = []
            if (src.page) parts.push(`Page ${src.page}`)
            if (src.section) parts.push(src.section)
            const subtitle = parts.join(' · ')
            return (
              <div key={i} style={{ marginBottom: 6, fontSize: 13 }}>
                <span>
                  📄 <strong>{src.filename}</strong>
                </span>
                {subtitle && (
                  <span style={{ color: '#666' }}> — {subtitle}</span>
                )}
                {src.source_url && (
                  <a
                    href={src.source_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ marginLeft: 8, fontSize: 12, color: '#0969da' }}
                  >
                    {isDriveLike(src) ? 'Open in Drive' : 'Open source'}
                  </a>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
