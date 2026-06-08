import type { Claim, GenerationSectionState, ReportTypeSection } from '../../types'

export function DraftEditor({
  claim,
  sections,
  streamSections,
  onSectionChange,
  onRegenerateSection,
}: {
  claim: Claim
  sections: ReportTypeSection[]
  streamSections?: Record<string, GenerationSectionState>
  onSectionChange: (key: string, content: string) => void
  onRegenerateSection?: (key: string) => void
}) {
  if (!sections.length) {
    return (
      <p style={{ fontSize: 13, color: '#888', margin: 0 }}>
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
              <h4 style={{ margin: '0 0 6px', fontSize: 14, color: '#0969da' }}>
                {labelByKey[key]}
                {streaming && (
                  <span style={{ marginLeft: 8, fontSize: 11, color: '#888' }}>streaming…</span>
                )}
              </h4>
              {onRegenerateSection && content.trim() ? (
                <button
                  type="button"
                  onClick={() => onRegenerateSection(key)}
                  style={{
                    fontSize: 11,
                    background: 'none',
                    border: '1px solid #d0d7de',
                    borderRadius: 4,
                    padding: '2px 8px',
                    cursor: 'pointer',
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
                border: '1px solid #d0d7de',
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
