import { useEffect, useState } from 'react'

import { suggestAddresses } from '../api/reportWriter'
import type { AddressSuggestion } from '../types'

type SuggestState = {
  suggestions: AddressSuggestion[]
  status: 'idle' | 'loading' | 'done' | 'error'
  error: string | null
}

const idleState: SuggestState = {
  suggestions: [],
  status: 'idle',
  error: null,
}

export function useAddressSuggest(query: string) {
  const trimmed = query.trim()
  const enabled = trimmed.length >= 3
  const [result, setResult] = useState<SuggestState>(idleState)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    const timer = setTimeout(() => {
      setResult(prev => ({ ...prev, status: 'loading', error: null }))
      suggestAddresses(trimmed)
        .then(suggestions => {
          if (cancelled) return
          setResult({
            suggestions,
            status: 'done',
            error: null,
          })
        })
        .catch(err => {
          if (cancelled) return
          setResult({
            suggestions: [],
            status: 'error',
            error: err instanceof Error ? err.message : 'Address search failed',
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
