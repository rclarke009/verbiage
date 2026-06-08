import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createClaim,
  deleteClaim,
  exportClaimDocx,
  getClaim,
  listClaims,
  listRuns,
  updateClaim,
  updateSection,
  uploadClaimImage,
} from '../../api/reportWriter'
import type { Claim } from '../../types'
import { useReportWriterStream } from '../../hooks/useReportWriterStream'
import { ClaimForm } from './ClaimForm'
import { ClaimList } from './ClaimList'
import { DraftEditor } from './DraftEditor'
import { GenerationProgress } from './GenerationProgress'
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
  const [draft, setDraft] = useState<Claim>(emptyClaim())
  const { state: genState, generating, generate, reset: resetStream } = useReportWriterStream()

  const claimsQuery = useQuery({
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

  useEffect(() => {
    if (claimQuery.data) setDraft(claimQuery.data)
  }, [claimQuery.data])

  const saveMutation = useMutation({
    mutationFn: () =>
      updateClaim(activeId!, {
        title: draft.title,
        field_notes: draft.field_notes,
        property_metadata: draft.property_metadata,
      }),
    onSuccess: data => {
      setDraft(data)
      queryClient.invalidateQueries({ queryKey: ['report-writer-claims'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: () => createClaim({ title: 'New claim', field_notes: '' }),
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ['report-writer-claims'] })
      setActiveId(data.claim_id)
    },
  })

  const sectionSaveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const handleSectionChange = useCallback(
    (key: string, content: string) => {
      setDraft(prev => ({
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
    [activeId],
  )

  const handleGenerate = async () => {
    if (!activeId) return
    await saveMutation.mutateAsync()
    resetStream()
    await generate(activeId, `/report-writer/claims/${activeId}/generate`)
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
    queryClient.invalidateQueries({ queryKey: ['report-writer-runs', activeId] })
  }

  const handleRegenerateSection = async (sectionKey: string) => {
    if (!activeId) return
    await generate(
      activeId,
      `/report-writer/claims/${activeId}/sections/${sectionKey}/regenerate`,
      { section_key: sectionKey },
    )
    queryClient.invalidateQueries({ queryKey: ['report-writer-claim', activeId] })
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!activeId || !e.target.files?.[0]) return
    await uploadClaimImage(activeId, e.target.files[0])
    e.target.value = ''
  }

  const sources =
    genState.retrievedSources.length > 0
      ? genState.retrievedSources
      : (Object.values(draft.sections ?? {})[0]?.sources ?? [])

  return (
    <div style={{ display: 'flex', gap: 20, minHeight: 'calc(100vh - 140px)' }}>
      <ClaimList
        claims={claimsQuery.data ?? []}
        activeId={activeId}
        onSelect={id => {
          setActiveId(id)
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
                disabled={generating || !draft.field_notes.trim()}
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
              <label style={{ fontSize: 13, cursor: 'pointer', padding: '6px 12px', border: '1px solid #d0d7de', borderRadius: 6 }}>
                Upload photo
                <input type="file" accept="image/*" hidden onChange={handleUpload} />
              </label>
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

            <GenerationProgress state={genState} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20 }}>
              <div>
                <ClaimForm
                  claim={draft}
                  onChange={patch => setDraft(prev => ({ ...prev, ...patch, property_metadata: patch.property_metadata ?? prev.property_metadata }))}
                />
                <hr style={{ margin: '20px 0', border: 'none', borderTop: '1px solid #d0d7de' }} />
                <DraftEditor
                  claim={draft}
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
    </div>
  )
}
