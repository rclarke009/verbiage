import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import type { Source } from '../../types'
import { downloadCitedSources } from '../../api/documents'
import { downloadableDocIds, uniqueSourcesByDoc } from '../../lib/uniqueSources'

interface Props {
  sources: Source[]
  chunksUsed?: number
  canDownload?: boolean
}

const btnStyle: CSSProperties = {
  background: 'none',
  border: '1px solid var(--app-border)',
  borderRadius: 4,
  padding: '2px 8px',
  cursor: 'pointer',
  fontSize: 12,
  color: 'var(--app-text-muted)',
}

export function SourceList({ sources, chunksUsed, canDownload = false }: Props) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const unique = useMemo(() => uniqueSourcesByDoc(sources), [sources])
  const downloadableIds = useMemo(() => downloadableDocIds(unique), [unique])

  useEffect(() => {
    setSelected(new Set(downloadableDocIds(uniqueSourcesByDoc(sources))))
    setError(null)
  }, [sources])

  if (!sources.length) return null

  const isDriveLike = (s: { source_type?: string; source?: string }) =>
    s.source_type === 'google_drive' || (s.source || '').toLowerCase().includes('drive')

  const toggle = (docId: string, downloadable: boolean) => {
    if (!downloadable) return
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(downloadableIds))

  const selectedItems = unique.filter(u => u.downloadable && selected.has(u.docId))

  const runDownload = async (items: { docId: string; filename: string }[]) => {
    if (!items.length || downloading) return
    setDownloading(true)
    setError(null)
    try {
      await downloadCitedSources(items)
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : 'Could not download sources')
    } finally {
      setDownloading(false)
    }
  }

  const showDownload = canDownload && downloadableIds.length > 0

  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: '1px solid var(--app-border)',
          borderRadius: 4,
          padding: '4px 10px',
          cursor: 'pointer',
          fontSize: 12,
          color: 'var(--app-text-muted)',
        }}
      >
        {open ? '▾' : '▸'} Sources ({unique.length})
        {chunksUsed !== undefined ? ` · ${chunksUsed} passages retrieved` : ''}
      </button>
      {open && (
        <div style={{ marginTop: 8, paddingLeft: 8, borderLeft: '3px solid var(--app-info-bg)' }}>
          {showDownload && (
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 6,
                alignItems: 'center',
                marginBottom: 10,
              }}
            >
              <button type="button" style={btnStyle} onClick={selectAll} disabled={downloading}>
                Select all
              </button>
              <button
                type="button"
                style={btnStyle}
                disabled={downloading || selectedItems.length === 0}
                onClick={() => runDownload(selectedItems.map(s => ({ docId: s.docId, filename: s.filename })))}
              >
                {downloading ? 'Downloading…' : 'Download selected'}
              </button>
              <button
                type="button"
                style={btnStyle}
                disabled={downloading}
                onClick={() => {
                  selectAll()
                  runDownload(unique.filter(u => u.downloadable).map(s => ({ docId: s.docId, filename: s.filename })))
                }}
              >
                Download all
              </button>
              {error && (
                <span style={{ fontSize: 12, color: 'var(--app-danger, #b42318)' }}>{error}</span>
              )}
            </div>
          )}
          {unique.map((src, i) => {
            const subtitle = src.sections.join(' · ')
            return (
              <div
                key={src.docId}
                style={{
                  marginBottom: i < unique.length - 1 ? 0 : 6,
                  paddingBottom: i < unique.length - 1 ? 8 : 0,
                  marginTop: i > 0 ? 8 : 0,
                  borderBottom:
                    i < unique.length - 1 ? '1px solid var(--app-border)' : undefined,
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                }}
              >
                {showDownload && (
                  <input
                    type="checkbox"
                    checked={src.downloadable && selected.has(src.docId)}
                    disabled={!src.downloadable || downloading}
                    onChange={() => toggle(src.docId, src.downloadable)}
                    aria-label={`Select ${src.filename}`}
                    style={{ marginTop: 3 }}
                  />
                )}
                <div>
                  <span>
                    📄 <strong>{src.filename}</strong>
                  </span>
                  {subtitle && (
                    <span style={{ color: 'var(--app-text-muted)' }}> — {subtitle}</span>
                  )}
                  {src.source_url && (
                    <a
                      href={src.source_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ marginLeft: 8, fontSize: 12, color: 'var(--app-primary)' }}
                    >
                      {isDriveLike(src) ? 'Open in Drive' : 'Open source'}
                    </a>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
