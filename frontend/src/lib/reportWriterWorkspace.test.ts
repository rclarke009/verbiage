import { describe, expect, it } from 'vitest'

import {
  claimHasGeneratedContent,
  defaultReportWriterWorkspace,
} from './reportWriterWorkspace'

describe('claimHasGeneratedContent', () => {
  it('is false when sections are empty or whitespace', () => {
    expect(claimHasGeneratedContent(undefined)).toBe(false)
    expect(claimHasGeneratedContent({})).toBe(false)
    expect(claimHasGeneratedContent({ intro: { content: '  ' } })).toBe(false)
  })

  it('is true when any section has text', () => {
    expect(claimHasGeneratedContent({ intro: { content: 'Hello' } })).toBe(true)
  })
})

describe('defaultReportWriterWorkspace', () => {
  it('returns intake for an empty draft', () => {
    expect(
      defaultReportWriterWorkspace({ hasGeneratedContent: false, generating: false }),
    ).toBe('intake')
  })

  it('returns report when a draft has content', () => {
    expect(
      defaultReportWriterWorkspace({ hasGeneratedContent: true, generating: false }),
    ).toBe('report')
  })

  it('returns report while generating', () => {
    expect(
      defaultReportWriterWorkspace({ hasGeneratedContent: false, generating: true }),
    ).toBe('report')
  })
})
