import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useFolders() {
  return useQuery({
    queryKey: ['folders'],
    queryFn: () => api.getFolders(),
    staleTime: 5 * 60_000,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
    staleTime: 60_000,
  })
}

export function useVersion() {
  return useQuery({
    queryKey: ['version'],
    queryFn: () => api.getVersion(),
    staleTime: 60_000,
  })
}

export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics(),
    staleTime: 30_000,
  })
}
