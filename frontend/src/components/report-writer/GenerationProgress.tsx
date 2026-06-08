import type { GenerationState } from '../../types'

export function GenerationProgress({ state }: { state: GenerationState }) {
  if (state.status === 'idle') return null
  const color =
    state.status === 'error'
      ? '#cf222e'
      : state.status === 'refused'
        ? '#bf8700'
        : state.status === 'running'
          ? '#0969da'
          : '#1a7f37'
  return (
    <div
      style={{
        padding: '8px 12px',
        borderRadius: 6,
        background: '#f6f8fa',
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
