import type { Claim } from '../types'

export type GenerateBlocker = { message: string; step: string }

export function getGenerateBlockers(
  draft: Pick<Claim, 'field_notes' | 'property_metadata'>,
): GenerateBlocker[] {
  const blockers: GenerateBlocker[] = []
  if (!draft.property_metadata?.report_type) {
    blockers.push({ message: 'Select a report type (Step 3)', step: '3' })
  }
  if (!draft.field_notes.trim()) {
    blockers.push({ message: 'Add field notes (Step 5)', step: '5' })
  }
  return blockers
}

export function canGenerateFromDraft(
  draft: Pick<Claim, 'field_notes' | 'property_metadata'>,
): boolean {
  return getGenerateBlockers(draft).length === 0
}

export function generateTitleFromBlockers(
  blockers: GenerateBlocker[],
  options?: { photoFolderHint?: string },
): string | undefined {
  if (blockers.length > 0) {
    return blockers[0].message
  }
  return options?.photoFolderHint
}
