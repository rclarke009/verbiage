interface Props {
  stats: {
    total_reports: number
    total_chunks: number
    avg_chunks_per_doc: number
  }
}

export function StatsBar({ stats }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        marginBottom: 16,
        flexWrap: 'wrap',
        fontSize: 13,
        color: '#24292f',
      }}
    >
      <span style={{ background: '#f6f8fa', padding: '8px 12px', borderRadius: 6 }}>
        <strong>{stats.total_reports}</strong> documents
      </span>
      <span style={{ background: '#f6f8fa', padding: '8px 12px', borderRadius: 6 }}>
        <strong>{stats.total_chunks}</strong> chunks
      </span>
      <span style={{ background: '#f6f8fa', padding: '8px 12px', borderRadius: 6 }}>
        Avg <strong>{stats.avg_chunks_per_doc}</strong> chunks/doc
      </span>
    </div>
  )
}
