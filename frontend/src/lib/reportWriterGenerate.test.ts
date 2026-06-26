import { describe, expect, it } from 'vitest'

import {
  canGenerateFromDraft,
  generateTitleFromBlockers,
  getGenerateBlockers,
} from './reportWriterGenerate'

describe('getGenerateBlockers', () => {
  it('returns both blockers when report type and field notes are missing', () => {
    expect(getGenerateBlockers({ field_notes: '', property_metadata: {} })).toEqual([
      { message: 'Select a report type (Step 3)', step: '3' },
      { message: 'Add field notes (Step 5)', step: '5' },
    ])
  })

  it('returns only field notes blocker when report type is set', () => {
    expect(
      getGenerateBlockers({
        field_notes: '  ',
        property_metadata: { report_type: 'roof' },
      }),
    ).toEqual([{ message: 'Add field notes (Step 5)', step: '5' }])
  })

  it('returns no blockers when prerequisites are met', () => {
    expect(
      getGenerateBlockers({
        field_notes: 'Damage on north slope.',
        property_metadata: { report_type: 'roof' },
      }),
    ).toEqual([])
  })
})

describe('canGenerateFromDraft', () => {
  it('is true when there are no blockers', () => {
    expect(
      canGenerateFromDraft({
        field_notes: 'Notes',
        property_metadata: { report_type: 'roof' },
      }),
    ).toBe(true)
  })

  it('is false when blockers exist', () => {
    expect(canGenerateFromDraft({ field_notes: '', property_metadata: {} })).toBe(false)
  })
})

describe('generateTitleFromBlockers', () => {
  it('returns first blocker message', () => {
    expect(
      generateTitleFromBlockers([
        { message: 'Select a report type (Step 3)', step: '3' },
        { message: 'Add field notes (Step 5)', step: '5' },
      ]),
    ).toBe('Select a report type (Step 3)')
  })

  it('returns photo folder hint when no blockers', () => {
    expect(
      generateTitleFromBlockers([], { photoFolderHint: 'Link a photo folder in Step 2' }),
    ).toBe('Link a photo folder in Step 2')
  })
})
