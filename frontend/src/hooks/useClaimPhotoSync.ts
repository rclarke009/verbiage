import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  cancelPhotoBatch,
  getClaimPhotoBatchStatus,
  getPhotoAnalysisCounts,
  retryStuckClaimPhotos,
  syncClaimPhotosFromDrive,
} from '../api/reportWriter'
import { isTransientHttpStatus } from '../lib/api'
import type { IngestBatchStatusResponse, PhotoAnalysisCounts } from '../types'

const POLL_MS = 2500
const POLL_MS_MAX = 30000

function isTransientPollError(err: unknown): boolean {
  if (err instanceof TypeError) {
    return true
  }
  if (!(err instanceof Error)) return false
  const msg = err.message.toLowerCase()
  return (
    msg.includes('502') ||
    msg.includes('503') ||
    msg.includes('504') ||
    msg.includes('service unavailable') ||
    msg.includes('bad gateway') ||
    msg.includes('gateway timeout') ||
    msg.includes('failed to fetch') ||
    msg.includes('network')
  )
}

function isTransientStatusResponse(status: number): boolean {
  return isTransientHttpStatus(status)
}

export function useClaimPhotoSync(claimId: string | null) {
  const queryClient = useQueryClient()
  const [batchId, setBatchId] = useState<string | null>(null)
  const [batchStatus, setBatchStatus] = useState<IngestBatchStatusResponse | null>(null)
  const [counts, setCounts] = useState<PhotoAnalysisCounts | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [pollReconnecting, setPollReconnecting] = useState(false)
  const [pollError, setPollError] = useState<string | null>(null)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollDelayRef = useRef(POLL_MS)
  const pollActiveRef = useRef(false)

  const refreshCounts = useCallback(async () => {
    if (!claimId) return
    try {
      const c = await getPhotoAnalysisCounts(claimId)
      setCounts(c)
    } catch {
      /* counts refresh is best-effort during poll blips */
    }
  }, [claimId])

  useEffect(() => {
    refreshCounts()
  }, [claimId, refreshCounts])

  const stopPoll = useCallback(() => {
    pollActiveRef.current = false
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
    pollDelayRef.current = POLL_MS
  }, [])

  const startPoll = useCallback(
    (id: string) => {
      stopPoll()
      setPollError(null)
      setPollReconnecting(false)
      pollDelayRef.current = POLL_MS
      pollActiveRef.current = true

      const tick = async () => {
        if (!pollActiveRef.current || !claimId) return
        try {
          const status = await getClaimPhotoBatchStatus(claimId, id)
          setBatchStatus(status)
          setPollReconnecting(false)
          setPollError(null)
          pollDelayRef.current = POLL_MS
          await refreshCounts()
          if (
            status.status === 'completed' ||
            status.status === 'failed' ||
            status.status === 'cancelled'
          ) {
            queryClient.invalidateQueries({ queryKey: ['claim-images', claimId] })
            stopPoll()
            return
          }
        } catch (err) {
          const httpStatus = (err as { status?: number }).status
          const transient =
            isTransientPollError(err) ||
            (typeof httpStatus === 'number' && isTransientStatusResponse(httpStatus))
          if (transient) {
            setPollReconnecting(true)
            pollDelayRef.current = Math.min(pollDelayRef.current * 2, POLL_MS_MAX)
          } else {
            stopPoll()
            setPollReconnecting(false)
            setPollError(err instanceof Error ? err.message : 'Photo status check failed')
            return
          }
        }
        if (pollActiveRef.current) {
          pollTimeoutRef.current = setTimeout(() => {
            void tick()
          }, pollDelayRef.current)
        }
      }

      void tick()
    },
    [claimId, queryClient, refreshCounts, stopPoll],
  )

  useEffect(() => () => stopPoll(), [stopPoll])

  const startSync = useCallback(
    async (folderId?: string) => {
      if (!claimId) return
      setSyncing(true)
      setSyncError(null)
      setPollError(null)
      try {
        const res = await syncClaimPhotosFromDrive(claimId, folderId)
        await refreshCounts()
        queryClient.invalidateQueries({ queryKey: ['claim-images', claimId] })
        if (res.batch_id) {
          setBatchId(res.batch_id)
          startPoll(res.batch_id)
        }
      } catch (err) {
        setSyncError(err instanceof Error ? err.message : 'Sync failed')
      } finally {
        setSyncing(false)
      }
    },
    [claimId, queryClient, refreshCounts, startPoll],
  )

  const retryStuck = useCallback(async () => {
    if (!claimId) return
    setRetrying(true)
    setSyncError(null)
    setPollError(null)
    try {
      const res = await retryStuckClaimPhotos(claimId)
      await refreshCounts()
      queryClient.invalidateQueries({ queryKey: ['claim-images', claimId] })
      if (res.batch_id) {
        setBatchId(res.batch_id)
        startPoll(res.batch_id)
      }
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : 'Retry failed')
    } finally {
      setRetrying(false)
    }
  }, [claimId, queryClient, refreshCounts, startPoll])

  const cancelAnalysis = useCallback(async () => {
    if (!claimId || !batchId) return
    setCancelling(true)
    try {
      await cancelPhotoBatch(claimId, batchId)
      stopPoll()
      const status = await getClaimPhotoBatchStatus(claimId, batchId)
      setBatchStatus(status)
      await refreshCounts()
      queryClient.invalidateQueries({ queryKey: ['claim-images', claimId] })
    } catch (err) {
      setPollError(err instanceof Error ? err.message : 'Cancel failed')
    } finally {
      setCancelling(false)
    }
  }, [batchId, claimId, queryClient, refreshCounts, stopPoll])

  const analysisActive =
    syncing ||
    retrying ||
    cancelling ||
    pollReconnecting ||
    (batchStatus != null &&
      batchStatus.status !== 'completed' &&
      batchStatus.status !== 'failed' &&
      batchStatus.status !== 'cancelled')

  return {
    batchId,
    batchStatus,
    counts,
    syncing,
    retrying,
    cancelling,
    analysisActive,
    syncError,
    pollReconnecting,
    pollError,
    startSync,
    retryStuck,
    cancelAnalysis,
    refreshCounts,
    watchBatch: startPoll,
  }
}
