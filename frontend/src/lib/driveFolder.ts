const FOLDER_IN_URL = /\/folders\/([a-zA-Z0-9_-]+)/
const RAW_ID = /^[a-zA-Z0-9_-]+$/
const DOC_IN_URL = /\/document\/d\/|\/file\/d\//

export const DRIVE_FOLDER_STORAGE_KEY = 'trueai_drive_folder_id'

export function parseDriveFolderInput(input: string): { id: string | null; error?: string } {
  const s = input.trim()
  if (!s) return { id: null }
  if (DOC_IN_URL.test(s) && !FOLDER_IN_URL.test(s)) {
    return { id: null, error: 'That looks like a single document link, not a folder.' }
  }
  const match = FOLDER_IN_URL.exec(s)
  if (match) return { id: match[1] }
  if (RAW_ID.test(s)) return { id: s }
  return { id: null, error: 'Could not parse a folder ID from that value.' }
}

export function driveFolderUrl(id: string): string {
  return `https://drive.google.com/drive/folders/${id}`
}

/** Folder id sent to the API: explicit parse, else team inbox when input is empty. */
export function resolveDriveFolderForApi(input: string, teamInboxId: string): string | undefined {
  const trimmed = input.trim()
  if (trimmed) {
    const { id } = parseDriveFolderInput(trimmed)
    return id ?? undefined
  }
  return teamInboxId || undefined
}
