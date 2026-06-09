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
  const { state: genState, generating, generate, reset: resetStream } = useReportWriterStream()
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
    await generate(activeId, `/report-writer/claims/${activeId}/generate`, undefined, sectionKeys)
    setLocalDraft(null)
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
    queryClient.invalidateQueries({ queryKey: ['report-writer-runs', activeId] })
  }

  const handleConfirmPhotoSync = async () => {
    if (!activeId) return
    await saveMutation.mutateAsync()
    const folderId = draft.property_metadata?.drive_photo_folder_id
    await photoSync.startSync(folderId)
  }

  const handleRegenerateSection = async (sectionKey: string) => {
    if (!activeId) return
    await generate(
      activeId,
      `/report-writer/claims/${activeId}/sections/${sectionKey}/regenerate`,
      { section_key: sectionKey },
      sectionKeys,
    )
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
          <p style={{ color: '#888', fontSize: 14 }}>
            Create or select a claim to draft a report from field notes and similar past reports.
          </p>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #d0d7de', cursor: 'pointer' }}
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
                  background: '#0969da',
                  color: '#fff',
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
                  setPdfLoading(true)
                  try {
                    const blob = await fetchClaimPdfBlob(activeId)
                    const url = URL.createObjectURL(blob)
                    setPdfPreviewUrl(prev => {
                      if (prev) URL.revokeObjectURL(prev)
                      return url
                    })
                  } catch (err) {
                    console.log('MYDEBUG →', err)
                    window.alert(err instanceof Error ? err.message : 'PDF preview failed')
                  } finally {
                    setPdfLoading(false)
                  }
                }}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #d0d7de', cursor: 'pointer' }}
              >
                {pdfLoading ? 'Loading PDF…' : 'Preview PDF'}
              </button>
              <button
                type="button"
                onClick={() => exportClaimDocx(activeId, draft.title)}
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #d0d7de', cursor: 'pointer' }}
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
                style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #cf222e', color: '#cf222e', cursor: 'pointer' }}
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
            />

            <GenerationProgress state={genState} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20 }}>
              <div>
                <ClaimForm
                  claim={draft}
                  claimId={activeId}
                  reportTypes={reportTypes}
                  typeLocked={hasGeneratedContent}
                  onChange={patch => updateDraft(prev => ({ ...prev, ...patch, property_metadata: patch.property_metadata ?? prev.property_metadata }))}
                  onConfirmPhotoSync={handleConfirmPhotoSync}
                  photoSyncing={photoSync.syncing}
                  photoSyncError={photoSync.syncError}
                />
                <hr style={{ margin: '20px 0', border: 'none', borderTop: '1px solid #d0d7de' }} />
                <DraftEditor
                  claim={draft}
                  sections={activeReportType?.sections ?? []}
                  streamSections={genState.status !== 'idle' ? genState.sections : undefined}
                  onSectionChange={handleSectionChange}
                  onRegenerateSection={handleRegenerateSection}
                />
              </div>
              <aside>
                <SourcesPanel sources={sources} />
                <hr style={{ margin: '16px 0', border: 'none', borderTop: '1px solid #d0d7de' }} />
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
              background: '#fff',
              borderRadius: 8,
              width: 'min(960px, 95vw)',
              height: 'min(90vh, 900px)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid #d0d7de' }}>
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
