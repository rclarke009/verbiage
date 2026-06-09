import type { GenerationState } from '../../types'

export function GenerationProgress({ state }: { state: GenerationState }) {
  if (state.status === 'idle') return null
  const color =
    state.status === 'error'
      ? 'var(--app-danger)'
      : state.status === 'refused'
        ? 'var(--app-warning)'
        : state.status === 'running'
          ? 'var(--app-primary)'
          : 'var(--app-success)'
  return (
    <div
      style={{
        padding: '8px 12px',
        borderRadius: 6,
        background: 'var(--app-surface)',
        fontSize: 13,
        marginBottom: 12,
        borderLeft: `4px solid ${color}`,
      }}
    >
      {state.status === 'running' && (
        <span>
          Generating draft… {state.activeNode ? `(step: ${state.activeNode})` : ''}
        </span>
      )}
      {state.status === 'complete' && <span>Draft generation complete.</span>}
      {state.status === 'refused' && (
        <span>Refused: {state.refusalReason || 'Retrieval too weak.'}</span>
      )}
      {state.status === 'error' && <span>Error: {state.error}</span>}
    </div>
  )
}
