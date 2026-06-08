import type { GenerationRun } from '../../types'

export function RunHistory({ runs }: { runs: GenerationRun[] }) {
  if (!runs.length) {
    return <p style={{ fontSize: 12, color: '#888' }}>No generation runs yet.</p>
  }
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 12 }}>
      {runs.slice(0, 8).map(r => (
        <li key={r.run_id} style={{ marginBottom: 6, color: '#57606a' }}>
          <span style={{ fontWeight: 600, color: '#24292f' }}>{r.status}</span>
          {' · '}
          {r.started_at ? new Date(r.started_at).toLocaleString() : r.run_id.slice(0, 8)}
        </li>
      ))}
    </ul>
  )
}
