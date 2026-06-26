import { useCallback, useRef, useState } from 'react'

import { fetchClaimPdfBlob } from '../api/reportWriter'

export function useClaimPdfPreview() {
  const [modalOpen, setModalOpen] = useState(false)
  const [iframeUrl, setIframeUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const cachedUrlRef = useRef<string | null>(null)
  const cachedClaimIdRef = useRef<string | null>(null)
  const inflightRef = useRef<{ claimId: string; promise: Promise<string | null> } | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const userInitiatedRef = useRef(false)

  const revokeCached = useCallback(() => {
    if (cachedUrlRef.current) {
      URL.revokeObjectURL(cachedUrlRef.current)
      cachedUrlRef.current = null
    }
    cachedClaimIdRef.current = null
  }, [])

  const invalidate = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    inflightRef.current = null
    userInitiatedRef.current = false
    revokeCached()
    setIframeUrl(null)
    setModalOpen(false)
    setLoading(false)
  }, [revokeCached])

  const storeBlob = useCallback(
    (claimId: string, blob: Blob): string => {
      revokeCached()
      const url = URL.createObjectURL(blob)
      cachedUrlRef.current = url
      cachedClaimIdRef.current = claimId
      return url
    },
    [revokeCached],
  )

  const fetchPdf = useCallback(
    async (claimId: string, signal: AbortSignal): Promise<string | null> => {
      const blob = await fetchClaimPdfBlob(claimId, signal)
      return storeBlob(claimId, blob)
    },
    [storeBlob],
  )

  const startFetch = useCallback(
    (claimId: string, userInitiated: boolean): Promise<string | null> => {
      if (cachedUrlRef.current && cachedClaimIdRef.current === claimId) {
        return Promise.resolve(cachedUrlRef.current)
      }

      if (inflightRef.current?.claimId === claimId) {
        return inflightRef.current.promise
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      userInitiatedRef.current = userInitiated

      if (userInitiated) {
        setLoading(true)
      }

      const promise = fetchPdf(claimId, controller.signal)
        .catch(err => {
          if (controller.signal.aborted) return null
          throw err
        })
        .finally(() => {
          if (abortRef.current === controller) {
            abortRef.current = null
          }
          if (userInitiatedRef.current && userInitiated) {
            userInitiatedRef.current = false
            setLoading(false)
          }
          if (inflightRef.current?.promise === promise) {
            inflightRef.current = null
          }
        })

      inflightRef.current = { claimId, promise }
      return promise
    },
    [fetchPdf],
  )

  const prefetch = useCallback(
    (claimId: string) => {
      if (cachedUrlRef.current && cachedClaimIdRef.current === claimId) return
      void startFetch(claimId, false).catch(err => {
        console.log('MYDEBUG →', err)
      })
    },
    [startFetch],
  )

  const openPreview = useCallback(
    async (claimId: string) => {
      if (cachedUrlRef.current && cachedClaimIdRef.current === claimId) {
        setIframeUrl(cachedUrlRef.current)
        setModalOpen(true)
        return
      }

      const inFlight = inflightRef.current?.claimId === claimId
      if (inFlight) {
        setLoading(true)
      }

      try {
        const url = await startFetch(claimId, !inFlight)
        if (!url) return
        setIframeUrl(url)
        setModalOpen(true)
      } catch (err) {
        console.log('MYDEBUG →', err)
        window.alert(err instanceof Error ? err.message : 'PDF preview failed')
      } finally {
        if (inFlight) {
          setLoading(false)
        }
      }
    },
    [startFetch],
  )

  const cancel = useCallback(() => {
    if (!loading) return
    abortRef.current?.abort()
    abortRef.current = null
    inflightRef.current = null
    userInitiatedRef.current = false
    setLoading(false)
  }, [loading])

  const closePreview = useCallback(() => {
    setModalOpen(false)
  }, [])

  return {
    modalOpen,
    iframeUrl,
    loading,
    prefetch,
    openPreview,
    invalidate,
    cancel,
    closePreview,
  }
}
