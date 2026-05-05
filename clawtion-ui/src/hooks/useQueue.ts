import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useQueueStore } from '@/stores/queueStore'

export function useQueueStatus() {
  const pollingInterval = useQueueStore((s) => s.pollingInterval)
  const autoPoll = useQueueStore((s) => s.autoPoll)

  return useQuery({
    queryKey: ['queue-status'],
    queryFn: () => api.getQueueStatus(),
    refetchInterval: autoPoll ? pollingInterval : false,
  })
}

export function usePendingJobs(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['queue-pending', limit, offset],
    queryFn: () => api.getQueuePending(limit, offset),
    refetchInterval: 10_000,
  })
}

export function useFailedJobs(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['queue-failed', limit, offset],
    queryFn: () => api.getQueueFailed(limit, offset),
    refetchInterval: 10_000,
  })
}

export function useProcessQueue() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.processQueue(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

export function useRetryJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (queueId: string) => api.retryQueueItem(queueId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

export function useClearFailed() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.clearFailedQueue(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}
