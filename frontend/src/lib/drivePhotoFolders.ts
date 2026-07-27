import type { DrivePhotoFolderRef, PropertyMetadata } from '../types'
import { parseDriveFolderInput } from './driveFolder'

/** Read a string field from property metadata (ignores non-strings). */
export function metaString(meta: PropertyMetadata | null | undefined, key: string): string {
  const v = meta?.[key]
  return typeof v === 'string' ? v : ''
}

/** Normalize claim metadata into a list of linked Drive photo folders. */
export function normalizeDrivePhotoFolders(meta: PropertyMetadata | null | undefined): DrivePhotoFolderRef[] {
  const m = meta ?? {}
  const raw = m.drive_photo_folders
  if (Array.isArray(raw)) {
    const out: DrivePhotoFolderRef[] = []
    const seen = new Set<string>()
    for (const entry of raw) {
      if (!entry || typeof entry !== 'object') continue
      const idRaw = (entry as { id?: unknown }).id
      const labelRaw = (entry as { label?: unknown }).label
      const id = typeof idRaw === 'string' ? idRaw.trim() : ''
      if (!id || seen.has(id)) continue
      seen.add(id)
      const label = typeof labelRaw === 'string' && labelRaw.trim() ? labelRaw.trim() : id
      out.push({ id, label })
    }
    return out
  }

  const legacyId = typeof m.drive_photo_folder_id === 'string' ? m.drive_photo_folder_id.trim() : ''
  if (!legacyId) return []
  const legacyLabel =
    typeof m.drive_photo_folder_label === 'string' && m.drive_photo_folder_label.trim()
      ? m.drive_photo_folder_label.trim()
      : legacyId
  return [{ id: legacyId, label: legacyLabel }]
}

/** Mirror first folder onto legacy keys; omit keys when the list is empty. */
export function mirrorDrivePhotoFolderFields(folders: DrivePhotoFolderRef[]): PropertyMetadata {
  if (!folders.length) {
    return {
      drive_photo_folders: [],
      drive_photo_folder_id: '',
      drive_photo_folder_label: '',
    }
  }
  return {
    drive_photo_folders: folders,
    drive_photo_folder_id: folders[0].id,
    drive_photo_folder_label: folders[0].label,
  }
}

export function setDrivePhotoFolders(
  meta: PropertyMetadata,
  folders: DrivePhotoFolderRef[],
): PropertyMetadata {
  return { ...meta, ...mirrorDrivePhotoFolderFields(folders) }
}

export function addDrivePhotoFolder(
  meta: PropertyMetadata,
  id: string,
  label: string,
): PropertyMetadata {
  const folders = normalizeDrivePhotoFolders(meta)
  if (folders.some(f => f.id === id)) {
    return setDrivePhotoFolders(meta, folders)
  }
  return setDrivePhotoFolders(meta, [...folders, { id, label }])
}

export function replaceDrivePhotoFolder(
  meta: PropertyMetadata,
  index: number,
  id: string,
  label: string,
): PropertyMetadata {
  const folders = normalizeDrivePhotoFolders(meta)
  if (index < 0 || index >= folders.length) {
    return addDrivePhotoFolder(meta, id, label)
  }
  const next = folders
    .map((f, i) => (i === index ? { id, label } : f))
    .filter((f, i, arr) => arr.findIndex(x => x.id === f.id) === i)
  return setDrivePhotoFolders(meta, next)
}

export function removeDrivePhotoFolder(meta: PropertyMetadata, index: number): PropertyMetadata {
  const folders = normalizeDrivePhotoFolders(meta).filter((_, i) => i !== index)
  return setDrivePhotoFolders(meta, folders)
}

/** Short label for pasted IDs/URLs (avoid dumping the full Drive URL into the UI). */
export function labelForLinkedFolder(id: string, rawInput?: string): string {
  const trimmed = (rawInput ?? '').trim()
  if (trimmed && !/drive\.google\.com/i.test(trimmed) && trimmed !== id) {
    return trimmed
  }
  if (id.length <= 12) return `Drive folder (${id})`
  return `Drive folder (${id.slice(0, 8)}…)`
}

/** Prefer a human folder name; rewrite stored Drive URLs to a short label. */
export function displayDriveFolderLabel(folder: { id: string; label: string }): string {
  const label = (folder.label || '').trim()
  if (!label || /drive\.google\.com/i.test(label) || label === folder.id) {
    return labelForLinkedFolder(folder.id)
  }
  return label
}

export function parseAndLinkFolder(
  input: string,
): { id: string; label: string } | { error: string } {
  const { id, error } = parseDriveFolderInput(input)
  if (!id) return { error: error ?? 'Could not parse folder' }
  return { id, label: labelForLinkedFolder(id, input) }
}
