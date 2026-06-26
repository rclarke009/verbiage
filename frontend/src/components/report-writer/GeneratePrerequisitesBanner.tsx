import type { GenerateBlocker } from '../../lib/reportWriterGenerate'

export function GeneratePrerequisitesBanner({
  blockers,
  generating = false,
}: {
  blockers: GenerateBlocker[]
  generating?: boolean
}) {
  if (generating || blockers.length === 0) return null

  return (
    <div
      style={{
        padding: '10px 12px',
        borderRadius: 6,
        background: 'var(--app-warning-bg)',
        borderLeft: '4px solid var(--app-warning)',
        fontSize: 13,
        marginBottom: 12,
      }}
    >
      <p style={{ margin: '0 0 6px', fontWeight: 600 }}>
        Complete these steps before generating a draft:
      </p>
      <ul style={{ margin: 0, paddingLeft: 20 }}>
        {blockers.map(blocker => (
          <li key={blocker.step}>{blocker.message}</li>
        ))}
      </ul>
    </div>
  )
}
