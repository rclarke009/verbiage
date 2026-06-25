import { useCallback, useState } from 'react'

import { SimilarTitlesDialog } from '../components/documents/SimilarTitlesDialog'
import { collectSimilarTitleWarnings } from '../lib/similarTitles'

import type { ProposedIngestItem, SimilarTitleWarning } from '../lib/similarTitles'

type PendingConfirm = {
  warnings: SimilarTitleWarning[]
  resolve: (confirmed: boolean) => void
}

export function useSimilarTitlesConfirm() {
  const [pending, setPending] = useState<PendingConfirm | null>(null)

  const confirmIngest = useCallback(async (items: ProposedIngestItem[]): Promise<boolean> => {
    if (!items.length) return true
    try {
      const warnings = await collectSimilarTitleWarnings(items)
      if (!warnings.length) return true
      return await new Promise<boolean>(resolve => {
        setPending({ warnings, resolve })
      })
    } catch (e) {
      console.log('MYDEBUG →', 'similar-titles check failed', e)
      return true
    }
  }, [])

  const close = useCallback((confirmed: boolean) => {
    setPending(current => {
      current?.resolve(confirmed)
      return null
    })
  }, [])

  const dialog = pending ? (
    <SimilarTitlesDialog
      warnings={pending.warnings}
      onConfirm={() => close(true)}
      onCancel={() => close(false)}
    />
  ) : null

  return { confirmIngest, dialog }
}
