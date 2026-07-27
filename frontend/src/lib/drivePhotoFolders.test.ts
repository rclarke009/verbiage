import { describe, expect, it } from 'vitest'

import {
  addDrivePhotoFolder,
  displayDriveFolderLabel,
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
  it('parses a Drive URL with a short label (not the raw URL)', () => {
    expect(
      parseAndLinkFolder('https://drive.google.com/drive/folders/1uQHiszkdkm2KFmLkSx2DmiCDHCzHX8OL'),
    ).toEqual({
      id: '1uQHiszkdkm2KFmLkSx2DmiCDHCzHX8OL',
      label: 'Drive folder (1uQHiszk…)',
    })
  })

  it('labels a raw folder id briefly', () => {
    expect(parseAndLinkFolder('folder_id_here_long')).toEqual({
      id: 'folder_id_here_long',
      label: 'Drive folder (folder_i…)',
    })
  })

  it('returns an error for bad input', () => {
    expect(parseAndLinkFolder('not a folder!!!')).toEqual({
      error: 'Could not parse a folder ID from that value.',
    })
  })
})

describe('displayDriveFolderLabel', () => {
  it('rewrites stored Drive URLs', () => {
    expect(
      displayDriveFolderLabel({
        id: '1uQHiszkdkm2KFmLkSx2DmiCDHCzHX8OL',
        label: 'https://drive.google.com/drive/u/1/folders/1uQHiszkdkm2KFmLkSx2DmiCDHCzHX8OL',
      }),
    ).toBe('Drive folder (1uQHiszk…)')
  })

  it('keeps real folder names', () => {
    expect(displayDriveFolderLabel({ id: 'abc', label: '123 Main St' })).toBe('123 Main St')
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
