import type { GenerationRun } from '../../types'

export function RunHistory({ runs }: { runs: GenerationRun[] }) {
  if (!runs.length) {
    return <p style={{ fontSize: 12, color: 'var(--app-text-subtle)' }}>No generation runs yet.</p>
  }
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 12 }}>
      {runs.slice(0, 8).map(r => (
        <li key={r.run_id} style={{ marginBottom: 6, color: 'var(--app-text-muted)' }}>
          <span style={{ fontWeight: 600, color: 'var(--app-text)' }}>{r.status}</span>
          {' · '}
          {r.started_at ? new Date(r.started_at).toLocaleString() : r.run_id.slice(0, 8)}
        </li>
      ))}
    </ul>
  )
}
