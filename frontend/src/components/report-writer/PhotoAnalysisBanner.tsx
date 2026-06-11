import type { IngestBatchStatusResponse, PhotoAnalysisCounts } from '../../types'

function damageClause(examined: number, withDamage: number): string {
  if (examined <= 0) return ''
  return ` (${withDamage} with damage so far)`
}

function analysisInFlight(
  syncing: boolean,
  pollReconnecting: boolean | undefined,
  batchStatus: IngestBatchStatusResponse | null,
  counts: PhotoAnalysisCounts | null,
): boolean {
  return (
    syncing ||
    !!pollReconnecting ||
    batchStatus?.status === 'pending' ||
    batchStatus?.status === 'running' ||
    (counts?.pending ?? 0) > 0 ||
    (counts?.running ?? 0) > 0
  )
}

export function PhotoAnalysisBanner({
  hasFolder,
  hasAddress,
  counts,
  batchStatus,
  syncing,
  retrying,
  cancelling,
  pollReconnecting,
  pollError,
  onRetryStuck,
  onCancel,
}: {
  hasFolder: boolean
  hasAddress: boolean
  counts: PhotoAnalysisCounts | null
  batchStatus: IngestBatchStatusResponse | null
  syncing: boolean
  retrying?: boolean
  cancelling?: boolean
  pollReconnecting?: boolean
  pollError?: string | null
  onRetryStuck?: () => void
  onCancel?: () => void
}) {
  if (!hasAddress && !hasFolder && !counts?.total) {
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
        Step 1: Enter the property address — we&apos;ll find the job photo folder in Drive.
      </div>
    )
  }

  const examined = counts?.succeeded ?? 0
  const total = counts?.total ?? 0
  const failed = counts?.failed ?? 0
  const withDamage = counts?.with_damage ?? 0
  const running = counts?.running ?? 0
  const showRetryStuck =
    !!onRetryStuck &&
    !syncing &&
    !retrying &&
    !cancelling &&
    (failed > 0 || running > 0 || !!pollReconnecting || !!pollError)

  const cancelButton =
    onCancel && analysisInFlight(syncing, pollReconnecting, batchStatus, counts) ? (
      <button
        type="button"
        disabled={cancelling}
        onClick={onCancel}
        style={{
          marginLeft: 8,
          padding: '4px 10px',
          borderRadius: 6,
          border: '1px solid var(--app-border)',
          background: 'var(--app-surface)',
          cursor: cancelling ? 'wait' : 'pointer',
          fontSize: 12,
        }}
      >
        {cancelling ? 'Cancelling…' : 'Cancel'}
      </button>
    ) : null

  const retryButton = showRetryStuck ? (
    <button
      type="button"
      disabled={retrying}
      onClick={onRetryStuck}
      style={{
        marginTop: 8,
        padding: '6px 12px',
        borderRadius: 6,
        border: '1px solid var(--app-border)',
        background: 'var(--app-surface)',
        cursor: retrying ? 'wait' : 'pointer',
        fontSize: 13,
      }}
    >
      {retrying ? 'Retrying…' : 'Retry stuck photos'}
    </button>
  ) : null

  if (pollError) {
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
        Photo status check stopped: {pollError}. Refresh the page or click Confirm &amp; start analysis
        again.
        {retryButton}
      </div>
    )
  }

  if (batchStatus?.status === 'cancelled') {
    const examinedAfterCancel = counts?.succeeded ?? 0
    const cancelledCount = batchStatus.cancelled ?? 0
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
        Photo analysis cancelled. {examinedAfterCancel} photo{examinedAfterCancel === 1 ? '' : 's'}{' '}
        examined before stop
        {cancelledCount > 0 ? `; ${cancelledCount} queued job${cancelledCount === 1 ? '' : 's'} skipped` : ''}.
        {retryButton}
      </div>
    )
  }

  const inFlight = analysisInFlight(syncing, pollReconnecting, batchStatus, counts)

  if (inFlight) {
    const batchDone = (batchStatus?.succeeded ?? 0) + (batchStatus?.skipped ?? 0)
    const batchTotal = batchStatus?.total ?? 0
    const progress =
      batchTotal > 0
        ? `${batchDone} of ${batchTotal} vision jobs`
        : `${examined} of ${total} examined${damageClause(examined, withDamage)}`
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: 'var(--app-surface)',
          borderLeft: '4px solid var(--app-primary)',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        Analyzing photos… {progress}.
        {pollReconnecting ? ' Server reconnecting — progress will resume shortly.' : ''} You can keep
        editing field notes. Cancel stops queued photos; the current one may finish.
        {cancelButton}
        {retryButton}
      </div>
    )
  }

  if (total > 0 && failed === 0) {
    const damageText =
      examined > 0
        ? `Examined ${examined} photo${examined === 1 ? '' : 's'}; ${withDamage} showed evidence of damage. `
        : `${total} photo${total === 1 ? '' : 's'} ready. `
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: 'var(--app-success-bg)',
          borderLeft: '4px solid var(--app-success)',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        {damageText}Generate when field notes are done.
      </div>
    )
  }

  if (failed > 0) {
    const damageText =
      examined > 0 ? `; ${withDamage} showed evidence of damage` : ''
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
        Examined {examined} of {total} photos{damageText}; {failed} failed. You can still generate a draft.
        {retryButton}
      </div>
    )
  }

  if (hasFolder && total === 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: 'var(--app-surface)',
          borderLeft: '4px solid var(--app-text-muted)',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        Folder linked — click Confirm &amp; start analysis to sync photos from Drive.
      </div>
    )
  }

  return null
}
