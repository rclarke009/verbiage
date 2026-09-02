import { useMemo, useState } from 'react'

import type {
  Claim,
  DocumentLayout,
  DocumentPhotoLayout,
  DocumentSpecimen,
  GenerationSectionState,
  ReportTypeSection,
  ReportWriterImage,
} from '../../types'

type OutlineKind = 'chrome' | 'section' | 'specimen' | 'photo'

type OutlineItem = {
  id: string
  kind: OutlineKind
  label: string
  hidden?: boolean
}

function defaultLayout(sections: ReportTypeSection[], images: ReportWriterImage[], reportType?: string): DocumentLayout {
  return {
    include_page_numbers: true,
    include_address_footer: true,
    include_engineering_letter: reportType === 'engineering',
    include_weather: true,
    starting_page_number: 1,
    section_order: sections.map(s => s.key),
    hidden_sections: [],
    specimens: [],
    photos: images.map((img, idx) => ({
      image_id: img.image_id,
      include: true,
      caption: (img.vision_analysis as { caption?: string } | undefined)?.caption || '',
      sort_order: img.sort_order ?? idx,
    })),
  }
}

function mergeLayout(
  claim: Claim,
  sections: ReportTypeSection[],
  images: ReportWriterImage[],
): DocumentLayout {
  const existing = claim.property_metadata?.document_layout
  const base = defaultLayout(sections, images, claim.property_metadata?.report_type)
  if (!existing) return base
  const photos = [...(existing.photos || [])]
  const known = new Set(photos.map(p => p.image_id))
  images.forEach((img, idx) => {
    if (known.has(img.image_id)) return
    photos.push({
      image_id: img.image_id,
      include: true,
      caption: (img.vision_analysis as { caption?: string } | undefined)?.caption || '',
      sort_order: img.sort_order ?? idx,
    })
  })
  return {
    ...base,
    ...existing,
    photos,
    specimens: existing.specimens || [],
    section_order: existing.section_order?.length ? existing.section_order : base.section_order,
    hidden_sections: existing.hidden_sections || [],
  }
}

export function DocumentCanvas({
  claim,
  sections,
  images,
  streamSections,
  onSectionChange,
  onRegenerateSection,
  regenerateDisabled,
  onLayoutChange,
}: {
  claim: Claim
  sections: ReportTypeSection[]
  images: ReportWriterImage[]
  streamSections?: Record<string, GenerationSectionState>
  onSectionChange: (key: string, content: string) => void
  onRegenerateSection?: (key: string) => void
  regenerateDisabled?: boolean
  onLayoutChange: (layout: DocumentLayout) => void
}) {
  const layout = useMemo(() => mergeLayout(claim, sections, images), [claim, sections, images])
  const [selected, setSelected] = useState<string>('chrome')
  const labelByKey = Object.fromEntries(sections.map(s => [s.key, s.label]))
  const hidden = new Set(layout.hidden_sections || [])
  const sectionOrder = (layout.section_order || sections.map(s => s.key)).filter(k =>
    sections.some(s => s.key === k),
  )
  for (const s of sections) {
    if (!sectionOrder.includes(s.key)) sectionOrder.push(s.key)
  }

  const outline: OutlineItem[] = [
    { id: 'chrome', kind: 'chrome', label: 'Page chrome' },
    ...sectionOrder.map(key => ({
      id: `section:${key}`,
      kind: 'section' as const,
      label: labelByKey[key] || key,
      hidden: hidden.has(key),
    })),
    ...(layout.specimens || []).map(spec => ({
      id: `specimen:${spec.id}`,
      kind: 'specimen' as const,
      label: spec.label,
      hidden: spec.include === false,
    })),
    ...(layout.photos || []).map((photo, idx) => ({
      id: `photo:${photo.image_id}`,
      kind: 'photo' as const,
      label: photo.caption?.trim() ? photo.caption.slice(0, 40) : `Photo ${idx + 1}`,
      hidden: photo.include === false,
    })),
  ]

  const patchLayout = (next: DocumentLayout) => onLayoutChange(next)

  const move = (list: string[], key: string, dir: -1 | 1) => {
    const i = list.indexOf(key)
    const j = i + dir
    if (i < 0 || j < 0 || j >= list.length) return list
    const copy = [...list]
    const [item] = copy.splice(i, 1)
    copy.splice(j, 0, item)
    return copy
  }

  const movePhotos = (imageId: string, dir: -1 | 1) => {
    const photos = [...(layout.photos || [])].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
    const i = photos.findIndex(p => p.image_id === imageId)
    const j = i + dir
    if (i < 0 || j < 0 || j >= photos.length) return
    const copy = [...photos]
    const [item] = copy.splice(i, 1)
    copy.splice(j, 0, item)
    patchLayout({
      ...layout,
      photos: copy.map((p, idx) => ({ ...p, sort_order: idx })),
    })
  }

  const selectedItem = outline.find(o => o.id === selected) || outline[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, minHeight: 420 }}>
      <nav
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 4,
          paddingBottom: 8,
          borderBottom: '1px solid var(--app-border)',
        }}
      >
        {outline.map(item => (
          <button
            key={item.id}
            type="button"
            onClick={() => setSelected(item.id)}
            style={{
              textAlign: 'left',
              padding: '6px 8px',
              borderRadius: 4,
              border: selected === item.id ? '1px solid var(--app-primary)' : '1px solid var(--app-border)',
              background: selected === item.id ? 'var(--app-info-bg)' : 'transparent',
              cursor: 'pointer',
              fontSize: 12,
              opacity: item.hidden ? 0.45 : 1,
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div style={{ minWidth: 0 }}>
        {selectedItem?.kind === 'chrome' ? (
          <ChromeEditor layout={layout} onChange={patchLayout} />
        ) : null}
        {selectedItem?.kind === 'section' ? (
          <SectionBlock
            sectionKey={selectedItem.id.slice('section:'.length)}
            label={selectedItem.label}
            claim={claim}
            streamSections={streamSections}
            hidden={hidden.has(selectedItem.id.slice('section:'.length))}
            onToggleHidden={() => {
              const key = selectedItem.id.slice('section:'.length)
              const nextHidden = hidden.has(key)
                ? (layout.hidden_sections || []).filter(k => k !== key)
                : [...(layout.hidden_sections || []), key]
              patchLayout({ ...layout, hidden_sections: nextHidden })
            }}
            onMove={dir =>
              patchLayout({ ...layout, section_order: move(sectionOrder, selectedItem.id.slice('section:'.length), dir) })
            }
            onSectionChange={onSectionChange}
            onRegenerateSection={onRegenerateSection}
            regenerateDisabled={regenerateDisabled}
          />
        ) : null}
        {selectedItem?.kind === 'specimen' ? (
          <SpecimenBlock
            specimen={(layout.specimens || []).find(s => `specimen:${s.id}` === selectedItem.id)}
            onChange={spec =>
              patchLayout({
                ...layout,
                specimens: (layout.specimens || []).map(s => (s.id === spec.id ? spec : s)),
              })
            }
          />
        ) : null}
        {selectedItem?.kind === 'photo' ? (
          <PhotoBlock
            photo={(layout.photos || []).find(p => `photo:${p.image_id}` === selectedItem.id)}
            onChange={photo =>
              patchLayout({
                ...layout,
                photos: (layout.photos || []).map(p => (p.image_id === photo.image_id ? photo : p)),
              })
            }
            onMove={dir => movePhotos(selectedItem.id.slice('photo:'.length), dir)}
          />
        ) : null}
      </div>
    </div>
  )
}

function ChromeEditor({
  layout,
  onChange,
}: {
  layout: DocumentLayout
  onChange: (layout: DocumentLayout) => void
}) {
  const toggle = (key: keyof DocumentLayout, value: boolean) => onChange({ ...layout, [key]: value })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <h4 style={{ margin: 0, fontSize: 14, color: 'var(--app-primary)' }}>Page chrome</h4>
      <label style={{ fontSize: 13 }}>
        <input
          type="checkbox"
          checked={layout.include_page_numbers !== false}
          onChange={e => toggle('include_page_numbers', e.target.checked)}
        />{' '}
        Include page numbers
      </label>
      <label style={{ fontSize: 13 }}>
        <input
          type="checkbox"
          checked={layout.include_address_footer !== false}
          onChange={e => toggle('include_address_footer', e.target.checked)}
        />{' '}
        Include address in footer
      </label>
      <label style={{ fontSize: 13 }}>
        <input
          type="checkbox"
          checked={layout.include_engineering_letter === true}
          onChange={e => toggle('include_engineering_letter', e.target.checked)}
        />{' '}
        Include engineering letter
      </label>
      <label style={{ fontSize: 13 }}>
        <input
          type="checkbox"
          checked={layout.include_weather !== false}
          onChange={e => toggle('include_weather', e.target.checked)}
        />{' '}
        Include weather
      </label>
    </div>
  )
}

function SectionBlock({
  sectionKey,
  label,
  claim,
  streamSections,
  hidden,
  onToggleHidden,
  onMove,
  onSectionChange,
  onRegenerateSection,
  regenerateDisabled,
}: {
  sectionKey: string
  label: string
  claim: Claim
  streamSections?: Record<string, GenerationSectionState>
  hidden: boolean
  onToggleHidden: () => void
  onMove: (dir: -1 | 1) => void
  onSectionChange: (key: string, content: string) => void
  onRegenerateSection?: (key: string) => void
  regenerateDisabled?: boolean
}) {
  const streamed = streamSections?.[sectionKey]
  const streaming = streamed?.streaming ?? false
  const streamedContent = streamed?.content ?? ''
  const savedContent = claim.sections?.[sectionKey]?.content ?? ''
  const content = streaming || streamedContent ? streamedContent : savedContent
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
        <h4 style={{ margin: '0 0 6px', fontSize: 14, color: 'var(--app-primary)' }}>{label}</h4>
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" onClick={() => onMove(-1)} style={{ fontSize: 11 }}>
            Up
          </button>
          <button type="button" onClick={() => onMove(1)} style={{ fontSize: 11 }}>
            Down
          </button>
          <button type="button" onClick={onToggleHidden} style={{ fontSize: 11 }}>
            {hidden ? 'Show in report' : 'Hide in report'}
          </button>
          {onRegenerateSection && content.trim() ? (
            <button type="button" disabled={regenerateDisabled} onClick={() => onRegenerateSection(sectionKey)} style={{ fontSize: 11 }}>
              Regenerate
            </button>
          ) : null}
        </div>
      </div>
      <textarea
        value={content}
        onChange={e => onSectionChange(sectionKey, e.target.value)}
        rows={10}
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
}

function SpecimenBlock({
  specimen,
  onChange,
}: {
  specimen?: DocumentSpecimen
  onChange: (specimen: DocumentSpecimen) => void
}) {
  if (!specimen) return <p style={{ fontSize: 13 }}>No specimen selected.</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h4 style={{ margin: 0, fontSize: 14, color: 'var(--app-primary)' }}>{specimen.label}</h4>
      <label style={{ fontSize: 13 }}>
        <input
          type="checkbox"
          checked={specimen.include !== false}
          onChange={e => onChange({ ...specimen, include: e.target.checked })}
        />{' '}
        Include in report
      </label>
      <label style={{ fontSize: 12 }}>
        Result
        <input
          value={specimen.result}
          onChange={e => onChange({ ...specimen, result: e.target.value })}
          style={{ width: '100%', marginTop: 4, padding: 6 }}
        />
      </label>
      <label style={{ fontSize: 12 }}>
        Notes
        <textarea
          value={specimen.notes}
          onChange={e => onChange({ ...specimen, notes: e.target.value })}
          rows={4}
          style={{ width: '100%', marginTop: 4, padding: 6 }}
        />
      </label>
    </div>
  )
}

function PhotoBlock({
  photo,
  onChange,
  onMove,
}: {
  photo?: DocumentPhotoLayout
  onChange: (photo: DocumentPhotoLayout) => void
  onMove: (dir: -1 | 1) => void
}) {
  if (!photo) return <p style={{ fontSize: 13 }}>No photo selected.</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h4 style={{ margin: 0, fontSize: 14, color: 'var(--app-primary)' }}>Photograph</h4>
      <label style={{ fontSize: 13 }}>
        <input
          type="checkbox"
          checked={photo.include !== false}
          onChange={e => onChange({ ...photo, include: e.target.checked })}
        />{' '}
        Include in report
      </label>
      <div style={{ display: 'flex', gap: 6 }}>
        <button type="button" onClick={() => onMove(-1)} style={{ fontSize: 11 }}>
          Move earlier
        </button>
        <button type="button" onClick={() => onMove(1)} style={{ fontSize: 11 }}>
          Move later
        </button>
      </div>
      <label style={{ fontSize: 12 }}>
        Caption
        <textarea
          value={photo.caption}
          onChange={e => onChange({ ...photo, caption: e.target.value })}
          rows={4}
          style={{ width: '100%', marginTop: 4, padding: 6 }}
        />
      </label>
    </div>
  )
}
