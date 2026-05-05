import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { ChunkItem } from '@/types/api'

interface ChunkNavigatorProps { currentChunkId: string; neighbors: ChunkItem[]; documentId: string }

export function ChunkNavigator({ currentChunkId, neighbors }: ChunkNavigatorProps) {
  const navigate = useNavigate()
  const currentIdx = neighbors.findIndex((c) => c.chunk_id === currentChunkId)
  const prev = currentIdx > 0 ? neighbors[currentIdx - 1] : null
  const next = currentIdx < neighbors.length - 1 ? neighbors[currentIdx + 1] : null

  return (
    <div className="flex items-center justify-between gap-4 py-4 mt-5 border-t border-border">
      {prev ? (
        <button onClick={() => navigate(`/search/chunks/${prev.chunk_id}`)}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-[12px] font-medium text-text-secondary hover:bg-hover transition-colors cursor-pointer">
          <ChevronLeft size={14} />Previous
        </button>
      ) : <div />}
      <span className="text-[11px] text-text-tertiary">{currentIdx + 1} / {neighbors.length}</span>
      {next ? (
        <button onClick={() => navigate(`/search/chunks/${next.chunk_id}`)}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-[12px] font-medium text-text-secondary hover:bg-hover transition-colors cursor-pointer">
          Next<ChevronRight size={14} />
        </button>
      ) : <div />}
    </div>
  )
}
