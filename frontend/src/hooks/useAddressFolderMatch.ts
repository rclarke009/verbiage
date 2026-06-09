import { useEffect, useState } from 'react'

import { matchDrivePhotoFolder } from '../api/reportWriter'
import type { DriveFolderMatch } from '../types'

type MatchState = {
  matches: DriveFolderMatch[]
  suggestedId: string | null
  status: 'idle' | 'searching' | 'done' | 'error'
  error: string | null
}

const idleState: MatchState = {
  matches: [],
  suggestedId: null,
  status: 'idle',
  error: null,
}

export function useAddressFolderMatch(address: string) {
  const trimmed = address.trim()
  const enabled = trimmed.length >= 5
  const [result, setResult] = useState<MatchState>(idleState)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    const timer = setTimeout(() => {
      setResult(prev => ({ ...prev, status: 'searching', error: null }))
      matchDrivePhotoFolder(trimmed)
        .then(data => {
          if (cancelled) return
          setResult({
            matches: data.matches,
            suggestedId: data.suggested_id ?? null,
            status: 'done',
            error: null,
          })
        })
        .catch(err => {
          if (cancelled) return
          setResult({
            matches: [],
            suggestedId: null,
            status: 'error',
            error: err instanceof Error ? err.message : 'Folder search failed',
          })
        })
    }, 500)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [trimmed, enabled])

  return enabled ? result : idleState
}
