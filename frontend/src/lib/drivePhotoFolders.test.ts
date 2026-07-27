import { describe, expect, it } from 'vitest'

import {
  addDrivePhotoFolder,
  metaString,
  normalizeDrivePhotoFolders,
  parseAndLinkFolder,
  removeDrivePhotoFolder,
  replaceDrivePhotoFolder,
  setDrivePhotoFolders,
} from './drivePhotoFolders'

describe('normalizeDrivePhotoFolders', () => {
  it('reads legacy single-id fields', () => {
    expect(
      normalizeDrivePhotoFolders({
        drive_photo_folder_id: 'folder_a',
        drive_photo_folder_label: 'Job A',
      }),
    ).toEqual([{ id: 'folder_a', label: 'Job A' }])
  })

  it('prefers drive_photo_folders list as source of truth', () => {
    expect(
      normalizeDrivePhotoFolders({
        drive_photo_folder_id: 'legacy',
        drive_photo_folders: [
          { id: 'f1', label: 'One' },
          { id: 'f2', label: 'Two' },
          { id: 'f1', label: 'Dup' },
        ],
      }),
    ).toEqual([
      { id: 'f1', label: 'One' },
      { id: 'f2', label: 'Two' },
    ])
  })

  it('treats empty drive_photo_folders as no folders even with legacy id', () => {
    expect(
      normalizeDrivePhotoFolders({
        drive_photo_folders: [],
        drive_photo_folder_id: 'legacy',
        drive_photo_folder_label: 'Legacy',
      }),
    ).toEqual([])
  })
})

describe('folder list mutations', () => {
  it('adds, replaces, and removes folders while mirroring legacy keys', () => {
    let meta = addDrivePhotoFolder({}, 'a', 'Folder A')
    expect(meta.drive_photo_folder_id).toBe('a')
    expect(meta.drive_photo_folder_label).toBe('Folder A')
    expect(normalizeDrivePhotoFolders(meta)).toEqual([{ id: 'a', label: 'Folder A' }])

    meta = addDrivePhotoFolder(meta, 'b', 'Folder B')
    expect(normalizeDrivePhotoFolders(meta)).toEqual([
      { id: 'a', label: 'Folder A' },
      { id: 'b', label: 'Folder B' },
    ])
    expect(meta.drive_photo_folder_id).toBe('a')

    meta = replaceDrivePhotoFolder(meta, 0, 'c', 'Folder C')
    expect(normalizeDrivePhotoFolders(meta)).toEqual([
      { id: 'c', label: 'Folder C' },
      { id: 'b', label: 'Folder B' },
    ])
    expect(meta.drive_photo_folder_id).toBe('c')

    meta = removeDrivePhotoFolder(meta, 0)
    expect(normalizeDrivePhotoFolders(meta)).toEqual([{ id: 'b', label: 'Folder B' }])
    expect(meta.drive_photo_folder_id).toBe('b')

    meta = removeDrivePhotoFolder(meta, 0)
    expect(normalizeDrivePhotoFolders(meta)).toEqual([])
    expect(meta.drive_photo_folder_id).toBe('')
  })

  it('skips duplicate add', () => {
    const meta = addDrivePhotoFolder(
      setDrivePhotoFolders({}, [{ id: 'a', label: 'A' }]),
      'a',
      'Again',
    )
    expect(normalizeDrivePhotoFolders(meta)).toEqual([{ id: 'a', label: 'A' }])
  })
})

describe('parseAndLinkFolder', () => {
  it('parses a Drive URL', () => {
    expect(parseAndLinkFolder('https://drive.google.com/drive/folders/abc_123')).toEqual({
      id: 'abc_123',
      label: 'https://drive.google.com/drive/folders/abc_123',
    })
  })

  it('returns an error for bad input', () => {
    expect(parseAndLinkFolder('not a folder!!!')).toEqual({
      error: 'Could not parse a folder ID from that value.',
    })
  })
})

describe('metaString', () => {
  it('returns strings and ignores non-strings', () => {
    expect(metaString({ address: '1 Main' }, 'address')).toBe('1 Main')
    expect(metaString({ drive_photo_folders: [{ id: 'x', label: 'X' }] }, 'drive_photo_folders')).toBe(
      '',
    )
  })
})
