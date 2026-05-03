import type { StatsResponse } from '../../types'

interface Props {
  stats: StatsResponse
}

export function StatsBar({ stats }: Props) {
  return (
    <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
      {[
        { label: 'Reports', value: stats.total_reports },
        { label: 'Total Chunks', value: stats.total_chunks.toLocaleString() },
        { label: 'Avg Chunks/Doc', value: stats.avg_chunks_per_doc },
      ].map(({ label, value }) => (
        <div key={label} style={{
          flex: 1, background: '#E3F2FD', borderRadius: 8, padding: '12px 16px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#1976D2' }}>{value}</div>
          <div style={{ fontSize: 12, color: '#555' }}>{label}</div>
        </div>
      ))}
    </div>
  )
}
