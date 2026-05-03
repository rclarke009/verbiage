import { useState } from 'react'
import type { Source } from '../../types'

interface Props {
  sources: Source[]
  chunksUsed?: number
}

export function SourceList({ sources, chunksUsed }: Props) {
  const [open, setOpen] = useState(false)
  if (!sources.length) return null

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none', border: '1px solid #ccc', borderRadius: 4,
          padding: '4px 10px', cursor: 'pointer', fontSize: 12, color: '#555',
        }}
      >
        {open ? '▾' : '▸'} Sources ({sources.length})
        {chunksUsed ? ` · ${chunksUsed} passages searched` : ''}
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
                <span>📄 <strong>{src.filename}</strong></span>
                {subtitle && <span style={{ color: '#666' }}> — {subtitle}</span>}
                {src.source_url && src.source_type === 'google_drive' && (
                  <a href={src.source_url} target="_blank" rel="noreferrer"
                    style={{ marginLeft: 8, fontSize: 12, color: '#1976D2' }}>
                    ☁️ Open in Drive
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
