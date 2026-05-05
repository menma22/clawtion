import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ChunkLevel, SearchRequest } from '@/types/api'

export function useSearch(
  type: 'semantic' | 'keyword' | 'hybrid',
  request: SearchRequest | null,
) {
  return useQuery({
    queryKey: ['search', type, request],
    queryFn: async () => {
      if (!request) throw new Error('No search request')
      return api.search(type, request)
    },
    enabled: !!request && request.query.length > 0,
    staleTime: 60_000,
  })
}

export function useChunks(documentId: string | undefined, level: ChunkLevel = 'file') {
  return useQuery({
    queryKey: ['chunks', documentId, level],
    queryFn: async () => {
      if (!documentId) throw new Error('No document ID')
      return api.getFileChunks(documentId, level)
    },
    enabled: !!documentId,
  })
}

export function useNeighborChunks(
  chunkId: string | undefined,
  before = 1,
  after = 1,
) {
  return useQuery({
    queryKey: ['neighbor-chunks', chunkId, before, after],
    queryFn: async () => {
      if (!chunkId) throw new Error('No chunk ID')
      return api.getNeighborChunks(chunkId, before, after)
    },
    enabled: !!chunkId,
  })
}

export function useParentChunk(chunkId: string | undefined) {
  return useQuery({
    queryKey: ['parent-chunk', chunkId],
    queryFn: async () => {
      if (!chunkId) throw new Error('No chunk ID')
      return api.getParentChunk(chunkId)
    },
    enabled: !!chunkId,
  })
}
