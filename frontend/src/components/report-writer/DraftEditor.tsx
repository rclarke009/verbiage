import type { Claim, GenerationSectionState, ReportTypeSection } from '../../types'

export function DraftEditor({
  claim,
  sections,
  streamSections,
  onSectionChange,
  onRegenerateSection,
  regenerateDisabled,
}: {
  claim: Claim
  sections: ReportTypeSection[]
  streamSections?: Record<string, GenerationSectionState>
  onSectionChange: (key: string, content: string) => void
  onRegenerateSection?: (key: string) => void
  regenerateDisabled?: boolean
}) {
  if (!sections.length) {
    return (
      <p style={{ fontSize: 13, color: 'var(--app-text-subtle)', margin: 0 }}>
        Select a report type to see draft sections.
      </p>
    )
  }

  const labelByKey = Object.fromEntries(sections.map(s => [s.key, s.label]))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {sections.map(({ key }) => {
        const streamed = streamSections?.[key]
        const saved = claim.sections?.[key]
        const content = streamed?.content ?? saved?.content ?? ''
        const streaming = streamed?.streaming ?? false
        return (
          <div key={key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ margin: '0 0 6px', fontSize: 14, color: 'var(--app-primary)' }}>
                {labelByKey[key]}
                {streaming && (
                  <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--app-text-subtle)' }}>streaming…</span>
                )}
              </h4>
              {onRegenerateSection && content.trim() ? (
                <button
                  type="button"
                  disabled={regenerateDisabled}
                  onClick={() => onRegenerateSection(key)}
                  style={{
                    fontSize: 11,
                    background: 'none',
                    border: '1px solid var(--app-border)',
                    borderRadius: 4,
                    padding: '2px 8px',
                    cursor: regenerateDisabled ? 'not-allowed' : 'pointer',
                    opacity: regenerateDisabled ? 0.6 : 1,
                  }}
                >
                  Regenerate
                </button>
              ) : null}
            </div>
            <textarea
              value={content}
              onChange={e => onSectionChange(key, e.target.value)}
              rows={5}
              style={{
                width: '100%',
                padding: 8,
                borderRadius: 6,
                border: '1px solid var(--app-border)',
                fontFamily: 'inherit',
                fontSize: 13,
                lineHeight: 1.5,
              }}
            />
          </div>
        )
      })}
    </div>
  )
}
