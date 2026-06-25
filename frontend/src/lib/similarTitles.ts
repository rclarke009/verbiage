import { fetchSimilarTitles } from '../api/documents'

import type { SimilarTitleMatch } from '../types'

export interface ProposedIngestItem {
  /** Title or filename to compare against the library. */
  proposed: string
  /** Display label in the warning dialog. */
  label?: string
  /** doc_ids to omit from matches (e.g. the same Drive file). */
  excludeDocIds?: string[]
}

export interface SimilarTitleWarning {
  proposed: string
  label: string
  matches: SimilarTitleMatch[]
}

function filterMatches(
  matches: SimilarTitleMatch[],
  excludeDocIds: string[] | undefined,
): SimilarTitleMatch[] {
  if (!excludeDocIds?.length) return matches
  const excluded = new Set(excludeDocIds)
  return matches.filter(m => !excluded.has(m.doc_id))
}

export async function collectSimilarTitleWarnings(
  items: ProposedIngestItem[],
  options?: { minRatio?: number },
): Promise<SimilarTitleWarning[]> {
  const warnings: SimilarTitleWarning[] = []
  const minRatio = options?.minRatio ?? 0.82

  await Promise.all(
    items.map(async item => {
      const proposed = item.proposed.trim()
      if (!proposed) return
      const { matches } = await fetchSimilarTitles(proposed, { minRatio })
      const filtered = filterMatches(matches, item.excludeDocIds)
      if (!filtered.length) return
      warnings.push({
        proposed,
        label: item.label?.trim() || proposed,
        matches: filtered,
      })
    }),
  )

  warnings.sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }))
  return warnings
}

export function formatSimilarityScore(score: number): string {
  return `${Math.round(score * 100)}%`
}
