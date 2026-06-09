import type { IngestBatchStatusResponse, PhotoAnalysisCounts } from '../../types'

export function PhotoAnalysisBanner({
  hasFolder,
  hasAddress,
  counts,
  batchStatus,
  syncing,
}: {
  hasFolder: boolean
  hasAddress: boolean
  counts: PhotoAnalysisCounts | null
  batchStatus: IngestBatchStatusResponse | null
  syncing: boolean
}) {
  if (!hasAddress && !hasFolder && !counts?.total) {
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: '#fff8c5',
          borderLeft: '4px solid #9a6700',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        Step 1: Enter the property address — we&apos;ll find the job photo folder in Drive.
      </div>
    )
  }

  const inFlight =
    syncing ||
    batchStatus?.status === 'pending' ||
    batchStatus?.status === 'running' ||
    (counts?.pending ?? 0) > 0 ||
    (counts?.running ?? 0) > 0

  const analyzed = counts?.succeeded ?? 0
  const total = counts?.total ?? 0
  const failed = counts?.failed ?? 0

  if (inFlight) {
    const batchDone = (batchStatus?.succeeded ?? 0) + (batchStatus?.skipped ?? 0)
    const batchTotal = batchStatus?.total ?? 0
    const progress =
      batchTotal > 0 ? `${batchDone} of ${batchTotal} vision jobs` : `${analyzed} of ${total} photos analyzed`
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: '#f6f8fa',
          borderLeft: '4px solid #0969da',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        Analyzing photos… {progress}. You can keep editing field notes.
      </div>
    )
  }

  if (total > 0 && failed === 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: '#dafbe1',
          borderLeft: '4px solid #1a7f37',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        {total} photo{total === 1 ? '' : 's'} ready. Generate when field notes are done.
      </div>
    )
  }

  if (failed > 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: '#fff8c5',
          borderLeft: '4px solid #9a6700',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        {analyzed} of {total} photos analyzed; {failed} failed. You can still generate a draft.
      </div>
    )
  }

  if (hasFolder && total === 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 6,
          background: '#f6f8fa',
          borderLeft: '4px solid #57606a',
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
