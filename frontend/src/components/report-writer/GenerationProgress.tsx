import type { CSSProperties } from 'react'
import type { GenerationState } from '../../types'

const cancelButtonStyle: CSSProperties = {
  marginLeft: 12,
  padding: '4px 10px',
  borderRadius: 6,
  border: '1px solid var(--app-border)',
  background: 'var(--app-surface)',
  cursor: 'pointer',
  fontSize: 12,
}

export function GenerationProgress({
  state,
  onCancel,
  cancelling,
}: {
  state: GenerationState
  onCancel?: () => void
  cancelling?: boolean
}) {
  if (state.status === 'idle') return null
  const color =
    state.status === 'error'
      ? 'var(--app-danger)'
      : state.status === 'refused'
        ? 'var(--app-warning)'
        : state.status === 'cancelled'
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
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        flexWrap: 'wrap',
      }}
    >
      <span>
        {state.status === 'running' && (
          <>
            Generating draft… {state.activeNode ? `(step: ${state.activeNode})` : ''}
          </>
        )}
        {state.status === 'complete' && <span>Draft generation complete.</span>}
        {state.status === 'refused' && (
          <span>Refused: {state.refusalReason || 'Retrieval too weak.'}</span>
        )}
        {state.status === 'cancelled' && (
          <span>Generation cancelled. Your saved draft was not changed.</span>
        )}
        {state.status === 'error' && <span>Error: {state.error}</span>}
      </span>
      {state.status === 'running' && onCancel && (
        <button
          type="button"
          onClick={onCancel}
          disabled={cancelling}
          style={cancelButtonStyle}
        >
          {cancelling ? 'Cancelling…' : 'Cancel'}
        </button>
      )}
    </div>
  )
}
