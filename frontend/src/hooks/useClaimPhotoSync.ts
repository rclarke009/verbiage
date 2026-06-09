import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  getClaimPhotoBatchStatus,
  getPhotoAnalysisCounts,
  syncClaimPhotosFromDrive,
} from '../api/reportWriter'
import { isTransientHttpStatus } from '../lib/api'
import type { IngestBatchStatusResponse, PhotoAnalysisCounts } from '../types'

const POLL_MS = 2500

function isTransientPollError(err: unknown): boolean {
  if (err instanceof TypeError) {
    // fetch network failure (offline, CORS blip, connection reset)
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
  const [syncError, setSyncError] = useState<string | null>(null)
  const [pollReconnecting, setPollReconnecting] = useState(false)
  const [pollError, setPollError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

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
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPoll = useCallback(
    (id: string) => {
      stopPoll()
      setPollError(null)
      setPollReconnecting(false)

      const tick = async () => {
        if (!claimId) return
        try {
          const status = await getClaimPhotoBatchStatus(claimId, id)
          setBatchStatus(status)
          setPollReconnecting(false)
          setPollError(null)
          await refreshCounts()
          queryClient.invalidateQueries({ queryKey: ['claim-images', claimId] })
          if (status.status === 'completed' || status.status === 'failed') {
            stopPoll()
          }
        } catch (err) {
          if (isTransientPollError(err)) {
            setPollReconnecting(true)
            return
          }
          const status = (err as { status?: number }).status
          if (typeof status === 'number' && isTransientStatusResponse(status)) {
            setPollReconnecting(true)
            return
          }
          stopPoll()
          setPollReconnecting(false)
          setPollError(err instanceof Error ? err.message : 'Photo status check failed')
        }
      }
      void tick()
      pollRef.current = setInterval(tick, POLL_MS)
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

  return {
    batchId,
    batchStatus,
    counts,
    syncing,
    syncError,
    pollReconnecting,
    pollError,
    startSync,
    refreshCounts,
  }
}
