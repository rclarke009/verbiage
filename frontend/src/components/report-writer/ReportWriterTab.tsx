import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createClaim,
  deleteClaim,
  downloadClaimPdf,
  exportClaimDocx,
  getClaim,
  importJobPackage,
  listClaimImages,
  listClaims,
  listReportTypes,
  listRuns,
  updateClaim,
  updateSection,
} from '../../api/reportWriter'
import type { Claim, DocumentLayout } from '../../types'
import { composeFullAddress } from '../../lib/address'
import {
  canGenerateFromDraft,
  generateTitleFromBlockers,
  getGenerateBlockers,
} from '../../lib/reportWriterGenerate'
import { useClaimPdfPreview } from '../../hooks/useClaimPdfPreview'
import { useClaimPhotoSync } from '../../hooks/useClaimPhotoSync'
import { useClaimWeather, clearWeatherMetadata } from '../../hooks/useClaimWeather'
import {
  useHistoricalAerials,
  clearHistoricalAerialsMetadata,
} from '../../hooks/useHistoricalAerials'
import { usePropertyMap, clearPropertyMapMetadata } from '../../hooks/usePropertyMap'
import {
  usePropertyAppraiser,
  clearPropertyAppraiserMetadata,
} from '../../hooks/usePropertyAppraiser'
import { useReportWriterStream } from '../../hooks/useReportWriterStream'
import { ClaimForm } from './ClaimForm'
import { ClaimList } from './ClaimList'
import { DocumentCanvas } from './DocumentCanvas'
import { GeneratePrerequisitesBanner } from './GeneratePrerequisitesBanner'
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
  const {
    modalOpen: pdfModalOpen,
    iframeUrl: pdfIframeUrl,
    loading: pdfLoading,
    prefetch: prefetchPdf,
    openPreview: openPdfPreview,
    invalidate: invalidatePdfPreview,
    cancel: cancelPdfPreview,
    closePreview: closePdfPreview,
    refreshLive: refreshPdfLive,
  } = useClaimPdfPreview()
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

  const {
    data: claims = [],
    isLoading: claimsLoading,
    error: claimsError,
  } = useQuery({
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
  const fullAddress = composeFullAddress(draft.property_metadata ?? {})
  const reportTypes = reportTypesQuery.data ?? []
  const activeReportType = reportTypes.find(t => t.id === draft.property_metadata?.report_type)
  const sectionKeys = activeReportType?.sections.map(s => s.key) ?? []
  const hasGeneratedContent = Object.values(draft.sections ?? {}).some(s => (s.content ?? '').trim())
  const generateBlockers = getGenerateBlockers(draft)
  const canGenerate = canGenerateFromDraft(draft)

  useEffect(() => {
    if (!activeId) return
    void refreshPdfLive(activeId)
  }, [activeId, refreshPdfLive])

  const updateDraft = useCallback(
    (updater: (prev: Claim) => Claim) => {
      setLocalDraft(prev => updater(prev ?? claimQuery.data ?? emptyClaim()))
    },
    [claimQuery.data],
  )

  const weather = useClaimWeather({
    claimId: activeId,
    address: fullAddress,
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
        property_metadata: clearWeatherMetadata(prev.property_metadata ?? {}),
      })),
  })

  const propertyMap = usePropertyMap({
    claimId: activeId,
    address: fullAddress,
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
    onPropertyMapClear: () =>
      updateDraft(prev => ({
        ...prev,
        property_metadata: clearPropertyMapMetadata(prev.property_metadata ?? {}),
      })),
  })

  const propertyAppraiser = usePropertyAppraiser({
    claimId: activeId,
    address: fullAddress,
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
    onPropertyAppraiserClear: () =>
      updateDraft(prev => ({
        ...prev,
        property_metadata: clearPropertyAppraiserMetadata(prev.property_metadata ?? {}),
      })),
  })

  const historicalAerials = useHistoricalAerials({
    claimId: activeId,
    address: fullAddress,
    stormDate: draft.property_metadata?.storm_date ?? '',
    stormDateIso: draft.property_metadata?.storm_date_iso ?? '',
    metadata: draft.property_metadata ?? {},
    onMetadataPatch: patch =>
      updateDraft(prev => {
        const nextMeta = { ...prev.property_metadata }
        for (const [k, v] of Object.entries(patch)) {
          if (v === '' || v === undefined) delete nextMeta[k]
          else nextMeta[k] = v as (typeof nextMeta)[string]
        }
        return { ...prev, property_metadata: nextMeta }
      }),
    onHistoricalAerialsClear: () =>
      updateDraft(prev => ({
        ...prev,
        property_metadata: clearHistoricalAerialsMetadata(prev.property_metadata ?? {}),
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

  const importMutation = useMutation({
    mutationFn: (file: File) => importJobPackage(file),
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ['report-writer-claims'] })
      setLocalDraft(null)
      setActiveId(data.claim_id)
      queryClient.invalidateQueries({ queryKey: ['report-writer-images', data.claim_id] })
    },
  })

  const imagesQuery = useQuery({
    queryKey: ['report-writer-images', activeId],
    queryFn: () => listClaimImages(activeId!),
    enabled: !!activeId,
  })

  const layoutSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pdfLiveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sectionSaveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const importInputRef = useRef<HTMLInputElement>(null)

  const flushPendingSectionSaves = useCallback(async () => {
    if (!activeId) return
    const timers = sectionSaveTimers.current
    const currentDraft = localDraft ?? claimQuery.data
    const pendingKeys = Object.keys(timers)
    await Promise.all(
      pendingKeys.map(async key => {
        clearTimeout(timers[key])
        delete timers[key]
        const content = currentDraft?.sections?.[key]?.content ?? ''
        await updateSection(activeId, key, content).catch(() => {})
      }),
    )
  }, [activeId, localDraft, claimQuery.data])

  const generateTitle = generateTitleFromBlockers(generateBlockers, {
    photoFolderHint: !draft.property_metadata?.drive_photo_folder_id
      ? 'Link a photo folder in Step 2 for better draft quality'
      : undefined,
  })

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
        updateSection(activeId, key, content)
          .then(() => {
            if (pdfLiveTimer.current) clearTimeout(pdfLiveTimer.current)
            pdfLiveTimer.current = setTimeout(() => {
              void refreshPdfLive(activeId)
            }, 600)
          })
          .catch(() => {})
      }, 800)
    },
    [activeId, refreshPdfLive, updateDraft],
  )

  const handleLayoutChange = useCallback(
    (layout: DocumentLayout) => {
      updateDraft(prev => ({
        ...prev,
        property_metadata: { ...prev.property_metadata, document_layout: layout },
      }))
      if (!activeId) return
      if (layoutSaveTimer.current) clearTimeout(layoutSaveTimer.current)
      layoutSaveTimer.current = setTimeout(() => {
        const meta = {
          ...(localDraft ?? claimQuery.data)?.property_metadata,
          document_layout: layout,
        }
        updateClaim(activeId, { property_metadata: meta })
          .then(() => {
            if (pdfLiveTimer.current) clearTimeout(pdfLiveTimer.current)
            pdfLiveTimer.current = setTimeout(() => {
              void refreshPdfLive(activeId)
            }, 400)
          })
          .catch(() => {})
      }, 500)
    },
    [activeId, claimQuery.data, localDraft, refreshPdfLive, updateDraft],
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
    await flushPendingSectionSaves()
    await saveMutation.mutateAsync()
    invalidatePdfPreview()
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
    prefetchPdf(activeId)
  }

  const handleCancelGeneration = async () => {
    await cancelGeneration()
    if (!activeId) return
    setLocalDraft(null)
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
  }

  const handleConfirmPhotoSync = async () => {
    if (!activeId) return
    await saveMutation.mutateAsync()
    // Do not pass folder_id — that overrides to a single folder. Sync all linked folders from claim metadata.
    await photoSync.startSync()
  }

  const handleRegenerateSection = async (sectionKey: string) => {
    if (!activeId || generating) return
    invalidatePdfPreview()
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
    prefetchPdf(activeId)
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
          invalidatePdfPreview()
          setActiveId(id)
          setLocalDraft(null)
          resetStream()
        }}
        onCreate={() => createMutation.mutate()}
        onImportPackage={() => importInputRef.current?.click()}
      />
      <input
        ref={importInputRef}
        type="file"
        accept=".zip,application/zip"
        style={{ display: 'none' }}
        onChange={e => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (file) importMutation.mutate(file)
        }}
      />

      <div style={{ flex: 1, minWidth: 0 }}>
        {(claimsError || reportTypesQuery.error || createMutation.error || importMutation.error) && (
          <p
            role="alert"
            style={{ color: 'var(--app-danger)', fontSize: 13, margin: '0 0 12px' }}
          >
            {(claimsError instanceof Error && claimsError.message) ||
              (reportTypesQuery.error instanceof Error && reportTypesQuery.error.message) ||
              (createMutation.error instanceof Error && createMutation.error.message) ||
              (importMutation.error instanceof Error && importMutation.error.message) ||
              'Could not load Report Writer.'}
          </p>
        )}
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
                title={generateTitle}
                style={{
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: 'none',
                  background: 'var(--app-primary)',
                  color: 'var(--app-on-primary)',
                  cursor: generating || !canGenerate ? 'not-allowed' : 'pointer',
                  opacity: generating || !canGenerate ? 0.6 : 1,
                }}
              >
                {generating ? 'Generating…' : 'Generate draft'}
              </button>
              <button
                type="button"
                disabled={pdfLoading}
                onClick={() => {
                  if (!activeId) return
                  void openPdfPreview(activeId)
                }}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
              >
                {pdfLoading ? 'Loading PDF…' : 'Preview PDF'}
              </button>
              {pdfLoading ? (
                <button
                  type="button"
                  onClick={() => cancelPdfPreview()}
                  style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
                >
                  Cancel PDF
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => downloadClaimPdf(activeId, draft.title, 'chapter')}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
              >
                Insert chapter PDF
              </button>
              <button
                type="button"
                onClick={() => exportClaimDocx(activeId, draft.title, 'pages')}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--app-border)', cursor: 'pointer' }}
              >
                Edit in Pages/Word
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

            <GeneratePrerequisitesBanner blockers={generateBlockers} generating={generating} />

            <PhotoAnalysisBanner
              hasAddress={!!fullAddress.trim()}
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

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(280px, 0.9fr) 240px', gap: 16 }}>
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
                  onUploadBatchStarted={batchId => {
                    photoSync.watchBatch(batchId)
                    void photoSync.refreshCounts()
                  }}
                  weatherLoading={weather.loading}
                  weatherError={weather.error}
                  weatherOptions={weather.options}
                  onRefreshWeather={weather.refresh}
                  onWeatherSelectionChange={weather.applySelectionPatch}
                  propertyMapLoading={propertyMap.loading}
                  propertyMapError={propertyMap.error}
                  propertyMapPreview={propertyMap.preview}
                  onRefreshPropertyMap={propertyMap.refresh}
                  onCachedImagesUnavailable={propertyMap.markCachedImagesUnavailable}
                  propertyAppraiserLoading={propertyAppraiser.loading}
                  propertyAppraiserError={propertyAppraiser.error}
                  propertyAppraiserPreview={propertyAppraiser.preview}
                  onRefreshPropertyAppraiser={propertyAppraiser.refresh}
                  onPropertyAppraiserCachedUnavailable={propertyAppraiser.markCachedImagesUnavailable}
                  historicalAerialsLoading={historicalAerials.loading}
                  historicalAerialsError={historicalAerials.error}
                  historicalAerialsPreview={historicalAerials.preview}
                  onRefreshHistoricalAerials={historicalAerials.refresh}
                  onHistoricalAerialsCachedUnavailable={historicalAerials.markCachedImagesUnavailable}
                  onHistoricalAerialIncludeChange={historicalAerials.setInclude}
                  onHistoricalAerialCommentChange={historicalAerials.setComment}
                  canGenerate={canGenerate}
                  generating={generating}
                  onGenerate={() => void handleGenerate()}
                  generateTitle={generateTitle}
                />
                <hr style={{ margin: '20px 0', border: 'none', borderTop: '1px solid var(--app-border)' }} />
                <DocumentCanvas
                  claim={draft}
                  sections={activeReportType?.sections ?? []}
                  images={imagesQuery.data ?? []}
                  streamSections={genState.status !== 'idle' ? genState.sections : undefined}
                  onSectionChange={handleSectionChange}
                  onRegenerateSection={handleRegenerateSection}
                  regenerateDisabled={generating}
                  onLayoutChange={handleLayoutChange}
                />
              </div>
              <aside style={{ minWidth: 0 }}>
                <h3 style={{ fontSize: 14, margin: '0 0 8px' }}>Live PDF</h3>
                {pdfIframeUrl ? (
                  <iframe
                    title="Report preview"
                    src={pdfIframeUrl}
                    style={{ width: '100%', height: 640, border: '1px solid var(--app-border)', borderRadius: 6, background: '#fff' }}
                  />
                ) : (
                  <p style={{ fontSize: 12, color: 'var(--app-text-subtle)' }}>
                    {pdfLoading ? 'Rendering preview…' : 'Save or edit a section to refresh the branded PDF.'}
                  </p>
                )}
              </aside>
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
      {pdfModalOpen && pdfIframeUrl ? (
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
          onClick={() => closePdfPreview()}
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
                onClick={() => closePdfPreview()}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 18 }}
              >
                ×
              </button>
            </div>
            <iframe title="Report PDF preview" src={pdfIframeUrl} style={{ flex: 1, border: 'none' }} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
