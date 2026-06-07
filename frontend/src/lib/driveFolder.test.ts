import { describe, expect, it } from 'vitest'
import {
  driveFolderUrl,
  parseDriveFolderInput,
  resolveDriveFolderForApi,
} from './driveFolder'

describe('parseDriveFolderInput', () => {
  it('parses a raw folder id', () => {
    expect(parseDriveFolderInput('abc123_xyz')).toEqual({ id: 'abc123_xyz' })
  })

  it('parses a full Drive folder URL', () => {
    const url = 'https://drive.google.com/drive/folders/12FGnoHObEnFRQNEUHtHla2Ajx33xauhc'
    expect(parseDriveFolderInput(url)).toEqual({ id: '12FGnoHObEnFRQNEUHtHla2Ajx33xauhc' })
  })

  it('rejects a single-document link', () => {
    const doc = 'https://docs.google.com/document/d/abc123/edit'
    expect(parseDriveFolderInput(doc)).toEqual({
      id: null,
      error: 'That looks like a single document link, not a folder.',
    })
  })

  it('returns null for empty input', () => {
    expect(parseDriveFolderInput('')).toEqual({ id: null })
    expect(parseDriveFolderInput('   ')).toEqual({ id: null })
  })

  it('returns an error for unparseable input', () => {
    expect(parseDriveFolderInput('not a folder!!!')).toEqual({
      id: null,
      error: 'Could not parse a folder ID from that value.',
    })
  })
})

describe('driveFolderUrl', () => {
  it('builds the canonical Drive folder URL', () => {
    expect(driveFolderUrl('abc123')).toBe('https://drive.google.com/drive/folders/abc123')
  })
})

describe('resolveDriveFolderForApi', () => {
  it('uses parsed id when input is set', () => {
    expect(resolveDriveFolderForApi('abc123', 'team-inbox')).toBe('abc123')
  })

  it('falls back to team inbox when input is empty', () => {
    expect(resolveDriveFolderForApi('', 'team-inbox')).toBe('team-inbox')
    expect(resolveDriveFolderForApi('   ', 'team-inbox')).toBe('team-inbox')
  })

  it('returns undefined when input is empty and no team inbox', () => {
    expect(resolveDriveFolderForApi('', '')).toBeUndefined()
  })
})
