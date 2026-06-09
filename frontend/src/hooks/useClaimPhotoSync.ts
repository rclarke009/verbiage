import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  getClaimPhotoBatchStatus,
  getPhotoAnalysisCounts,
  syncClaimPhotosFromDrive,
} from '../api/reportWriter'
import type { IngestBatchStatusResponse, PhotoAnalysisCounts } from '../types'

const POLL_MS = 2500

export function useClaimPhotoSync(claimId: string | null) {
  const queryClient = useQueryClient()
  const [batchId, setBatchId] = useState<string | null>(null)
  const [batchStatus, setBatchStatus] = useState<IngestBatchStatusResponse | null>(null)
  const [counts, setCounts] = useState<PhotoAnalysisCounts | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshCounts = useCallback(async () => {
    if (!claimId) return
    try {
      const c = await getPhotoAnalysisCounts(claimId)
      setCounts(c)
    } catch {
      /* ignore */
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
      const tick = async () => {
        if (!claimId) return
        try {
          const status = await getClaimPhotoBatchStatus(claimId, id)
          setBatchStatus(status)
          await refreshCounts()
          queryClient.invalidateQueries({ queryKey: ['claim-images', claimId] })
          if (status.status === 'completed' || status.status === 'failed') {
            stopPoll()
          }
        } catch {
          stopPoll()
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
    startSync,
    refreshCounts,
  }
}
