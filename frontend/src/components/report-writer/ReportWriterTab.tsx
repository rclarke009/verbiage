import { useCallback, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createClaim,
  deleteClaim,
  exportClaimDocx,
  fetchClaimPdfBlob,
  getClaim,
  listClaims,
  listReportTypes,
  listRuns,
  updateClaim,
  updateSection,
} from '../../api/reportWriter'
import type { Claim } from '../../types'
import { useClaimPhotoSync } from '../../hooks/useClaimPhotoSync'
import { useClaimWeather, clearWeatherMetadata } from '../../hooks/useClaimWeather'
import { useReportWriterStream } from '../../hooks/useReportWriterStream'
import { ClaimForm } from './ClaimForm'
import { ClaimList } from './ClaimList'
import { DraftEditor } from './DraftEditor'
import { GenerationProgress } from './GenerationProgress'
import { PhotoAnalysisBanner } from './PhotoAnalysisBanner'
import { RunHistory } from './RunHistory'
import { SourcesPanel } from './SourcesPanel'

const emptyClaim = (): Claim => ({
  claim_id: '',
  user_id: '',
  title: '',
  property_metadata: {},
  field_notes: '',
  status: 'draft',
  sections: {},
})

export function ReportWriterTab() {
  const queryClient = useQueryClient()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [localDraft, setLocalDraft] = useState<Claim | null>(null)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const pdfAbortRef = useRef<AbortController | null>(null)
  const {
    state: genState,
    generating,
    cancelling,
    generate,
    cancel: cancelGeneration,
    reset: resetStream,
  } = useReportWriterStream()
  const photoSync = useClaimPhotoSync(activeId)

  const reportTypesQuery = useQuery({
    queryKey: ['report-writer-types'],
    queryFn: listReportTypes,
  })

  const { data: claims = [], isLoading: claimsLoading } = useQuery({
    queryKey: ['report-writer-claims'],
    queryFn: listClaims,
  })

  const claimQuery = useQuery({
    queryKey: ['report-writer-claim', activeId],
    queryFn: () => getClaim(activeId!),
    enabled: !!activeId,
  })

  const runsQuery = useQuery({
    queryKey: ['report-writer-runs', activeId],
    queryFn: () => listRuns(activeId!),
    enabled: !!activeId,
  })

  const draft = localDraft ?? claimQuery.data ?? emptyClaim()
  const reportTypes = reportTypesQuery.data ?? []
  const activeReportType = reportTypes.find(t => t.id === draft.property_metadata?.report_type)
  const sectionKeys = activeReportType?.sections.map(s => s.key) ?? []
  const hasGeneratedContent = Object.values(draft.sections ?? {}).some(s => (s.content ?? '').trim())
  const canGenerate = !!draft.property_metadata?.report_type && !!draft.field_notes.trim()

  const updateDraft = useCallback(
    (updater: (prev: Claim) => Claim) => {
      setLocalDraft(prev => updater(prev ?? claimQuery.data ?? emptyClaim()))
    },
    [claimQuery.data],
  )

  const weather = useClaimWeather({
    claimId: activeId,
    address: draft.property_metadata?.address ?? '',
    stormDate: draft.property_metadata?.storm_date ?? '',
    stormDateIso: draft.property_metadata?.storm_date_iso ?? '',
    metadata: draft.property_metadata ?? {},
    onMetadataPatch: patch =>
      updateDraft(prev => {
        const nextMeta = { ...prev.property_metadata }
        for (const [k, v] of Object.entries(patch)) {
          if (v === '') delete nextMeta[k]
          else if (v !== undefined) nextMeta[k] = v
        }
        return { ...prev, property_metadata: nextMeta }
      }),
    onWeatherClear: () =>
      updateDraft(prev => ({
        ...prev,
        property_metadata: clearWeatherMetadata(prev.property_metadata ?? {}) as Record<string, string>,
      })),
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      updateClaim(activeId!, {
        title: draft.title,
        field_notes: draft.field_notes,
        property_metadata: draft.property_metadata,
      }),
    onSuccess: data => {
      setLocalDraft(data)
      queryClient.invalidateQueries({ queryKey: ['report-writer-claims'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: () => createClaim({ title: 'New claim', field_notes: '' }),
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ['report-writer-claims'] })
      setLocalDraft(null)
      setActiveId(data.claim_id)
    },
  })

  const sectionSaveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const handleSectionChange = useCallback(
    (key: string, content: string) => {
      updateDraft(prev => ({
        ...prev,
        sections: {
          ...prev.sections,
          [key]: { section_key: key, content, sources: prev.sections?.[key]?.sources ?? [] },
        },
      }))
      if (!activeId) return
      const timers = sectionSaveTimers.current
      if (timers[key]) clearTimeout(timers[key])
      timers[key] = setTimeout(() => {
        updateSection(activeId, key, content).catch(() => {})
      }, 800)
    },
    [activeId, updateDraft],
  )

  const handleGenerate = async () => {
    if (!activeId) return
    const pending =
      (photoSync.counts?.pending ?? 0) + (photoSync.counts?.running ?? 0)
    if (pending > 0) {
      const ok = window.confirm(
        `${pending} photo(s) still analyzing. Generate draft anyway?`,
      )
      if (!ok) return
    }
    await saveMutation.mutateAsync()
    resetStream()
    const wasCancelled = await generate(
      activeId,
      `/report-writer/claims/${activeId}/generate`,
      undefined,
      sectionKeys,
    )
    if (wasCancelled) {
      setLocalDraft(null)
      queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
      return
    }
    setLocalDraft(null)
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
    queryClient.invalidateQueries({ queryKey: ['report-writer-runs', activeId] })
  }

  const handleCancelGeneration = async () => {
    await cancelGeneration()
    if (!activeId) return
    setLocalDraft(null)
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
  }

  const handleCancelPdfPreview = () => {
    pdfAbortRef.current?.abort()
    pdfAbortRef.current = null
    setPdfLoading(false)
  }

  const handleConfirmPhotoSync = async () => {
    if (!activeId) return
    await saveMutation.mutateAsync()
    const folderId = draft.property_metadata?.drive_photo_folder_id
    await photoSync.startSync(folderId)
  }

  const handleRegenerateSection = async (sectionKey: string) => {
    if (!activeId || generating) return
    const wasCancelled = await generate(
      activeId,
      `/report-writer/claims/${activeId}/sections/${sectionKey}/regenerate`,
      { section_key: sectionKey },
      sectionKeys,
    )
    if (wasCancelled) {
      setLocalDraft(null)
      queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
      return
    }
    setLocalDraft(null)
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
  }

  const sources =
    genState.retrievedSources.length > 0
      ? genState.retrievedSources
      : (Object.values(draft.sections ?? {})[0]?.sources ?? [])

  return (
    <div style={{ display: 'flex', gap: 20, minHeight: 'calc(100vh - 140px)' }}>
      <ClaimList
        claims={claims}
        loading={claimsLoading}
        activeId={activeId}
        reportTypes={reportTypes}
        onSelect={id => {
          setActiveId(id)
          setLocalDraft(null)
          resetStream()
        }}
        onCreate={() => createMutation.mutate()}
      />

      <div style={{ flex: 1, minWidth: 0 }}>
        {!activeId ? (
          <p style={{ color: 'var(--app-text-subtle)', fontSize: 14 }}>
            Create or select a claim to draft a report from field notes and similar past reports.
          </p>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
              >
                Save
              </button>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={generating || !canGenerate}
                title={
                  !draft.property_metadata?.report_type
                    ? 'Select a report type first'
                    : !draft.property_metadata?.drive_photo_folder_id
                      ? 'Link a photo folder in Step 2 for better draft quality'
                      : undefined
                }
                style={{
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: 'none',
                  background: 'var(--app-primary)',
                  color: 'var(--app-on-primary)',
                  cursor: 'pointer',
                }}
              >
                {generating ? 'Generating…' : 'Generate draft'}
              </button>
              <button
                type="button"
                disabled={pdfLoading}
                onClick={async () => {
                  if (!activeId) return
                  pdfAbortRef.current?.abort()
                  const controller = new AbortController()
                  pdfAbortRef.current = controller
                  setPdfLoading(true)
                  try {
                    const blob = await fetchClaimPdfBlob(activeId, controller.signal)
                    const url = URL.createObjectURL(blob)
                    setPdfPreviewUrl(prev => {
                      if (prev) URL.revokeObjectURL(prev)
                      return url
                    })
                  } catch (err) {
                    if (controller.signal.aborted) return
                    console.log('MYDEBUG →', err)
                    window.alert(err instanceof Error ? err.message : 'PDF preview failed')
                  } finally {
                    if (pdfAbortRef.current === controller) {
                      pdfAbortRef.current = null
                    }
                    setPdfLoading(false)
                  }
                }}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
              >
                {pdfLoading ? 'Loading PDF…' : 'Preview PDF'}
              </button>
              {pdfLoading ? (
                <button
                  type="button"
                  onClick={handleCancelPdfPreview}
                  style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
                >
                  Cancel PDF
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => exportClaimDocx(activeId, draft.title)}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
              >
                Export DOCX
              </button>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm('Delete this claim?')) {
                    deleteClaim(activeId).then(() => {
                      setActiveId(null)
                      queryClient.invalidateQueries({ queryKey: ['report-writer-claims'] })
                    })
                  }
                }}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-danger)', color: 'var(--app-danger)', cursor: 'pointer' }}
              >
                Delete
              </button>
            </div>

            <PhotoAnalysisBanner
              hasAddress={!!draft.property_metadata?.address?.trim()}
              hasFolder={!!draft.property_metadata?.drive_photo_folder_id}
              counts={photoSync.counts}
              batchStatus={photoSync.batchStatus}
              syncing={photoSync.syncing}
              retrying={photoSync.retrying}
              cancelling={photoSync.cancelling}
              pollReconnecting={photoSync.pollReconnecting}
              pollError={photoSync.pollError}
              onRetryStuck={() => void photoSync.retryStuck()}
              onCancel={
                photoSync.batchId && photoSync.analysisActive
                  ? () => void photoSync.cancelAnalysis()
                  : undefined
              }
            />

            <GenerationProgress
              state={genState}
              onCancel={generating ? () => void handleCancelGeneration() : undefined}
              cancelling={cancelling}
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20 }}>
              <div style={{ minWidth: 0 }}>
                <ClaimForm
                  claim={draft}
                  claimId={activeId}
                  reportTypes={reportTypes}
                  typeLocked={hasGeneratedContent}
                  onChange={patch => updateDraft(prev => ({ ...prev, ...patch, property_metadata: patch.property_metadata ?? prev.property_metadata }))}
                  onConfirmPhotoSync={handleConfirmPhotoSync}
                  photoSyncing={photoSync.syncing}
                  photoSyncError={photoSync.syncError}
                  photoCounts={photoSync.counts}
                  weatherLoading={weather.loading}
                  weatherError={weather.error}
                  weatherOptions={weather.options}
                  onRefreshWeather={weather.refresh}
                  onWeatherSelectionChange={weather.applySelectionPatch}
                />
                <hr style={{ margin: '20px 0', border: 'none', borderTop: '1px solid var(--app-border)' }} />
                <DraftEditor
                  claim={draft}
                  sections={activeReportType?.sections ?? []}
                  streamSections={genState.status !== 'idle' ? genState.sections : undefined}
                  onSectionChange={handleSectionChange}
                  onRegenerateSection={handleRegenerateSection}
                  regenerateDisabled={generating}
                />
              </div>
              <aside>
                <SourcesPanel sources={sources} />
                <hr style={{ margin: '16px 0', border: 'none', borderTop: '1px solid var(--app-border)' }} />
                <h3 style={{ fontSize: 14, margin: '0 0 8px' }}>Run history</h3>
                <RunHistory runs={runsQuery.data ?? []} />
              </aside>
            </div>
          </>
        )}
      </div>
      {pdfPreviewUrl ? (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 24,
          }}
          onClick={() => {
            URL.revokeObjectURL(pdfPreviewUrl)
            setPdfPreviewUrl(null)
          }}
        >
          <div
            style={{
              background: 'var(--app-bg)',
              borderRadius: 8,
              width: 'min(960px, 95vw)',
              height: 'min(90vh, 900px)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid var(--app-border)' }}>
              <strong style={{ fontSize: 14 }}>Report preview</strong>
              <button
                type="button"
                onClick={() => {
                  URL.revokeObjectURL(pdfPreviewUrl)
                  setPdfPreviewUrl(null)
                }}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 18 }}
              >
                ×
              </button>
            </div>
            <iframe title="Report PDF preview" src={pdfPreviewUrl} style={{ flex: 1, border: 'none' }} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
