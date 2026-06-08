import type { ReportWriterSource } from '../../types'

const SECTION_LABELS: Record<string, string> = {
  property_overview: 'Property Overview',
  roof_observations: 'Roof Observations',
  interior_observations: 'Interior Observations',
  conclusion: 'Conclusion',
}

export function SourcesPanel({
  sources,
  title = 'Retrieved sources',
}: {
  sources: ReportWriterSource[]
  title?: string
}) {
  if (!sources.length) {
    return (
      <p style={{ fontSize: 13, color: '#888', margin: 0 }}>
        Sources from similar past reports appear here after retrieval.
      </p>
    )
  }
  return (
    <div>
      <h3 style={{ margin: '0 0 10px', fontSize: 14, color: '#24292f' }}>{title}</h3>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {sources.map((s, i) => (
          <li
            key={`${s.chunk_id}-${i}`}
            style={{
              marginBottom: 10,
              padding: 10,
              background: '#f6f8fa',
              borderRadius: 6,
              fontSize: 12,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              {s.document_title || s.doc_id || 'Document'}
            </div>
            <div style={{ color: '#57606a', lineHeight: 1.45 }}>{s.snippet}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export { SECTION_LABELS }
