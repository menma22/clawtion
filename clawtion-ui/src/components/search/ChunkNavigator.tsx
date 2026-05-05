import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import type { ChunkItem } from '@/types/api'

interface ChunkNavigatorProps {
  currentChunkId: string
  neighbors: ChunkItem[]
  documentId: string
}

export function ChunkNavigator({
  currentChunkId,
  neighbors,
}: ChunkNavigatorProps) {
  const navigate = useNavigate()
  const currentIdx = neighbors.findIndex((c) => c.chunk_id === currentChunkId)
  const prev = currentIdx > 0 ? neighbors[currentIdx - 1] : null
  const next = currentIdx < neighbors.length - 1 ? neighbors[currentIdx + 1] : null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex items-center justify-between gap-4 py-4 border-t border-border-default mt-6"
    >
      {prev ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/search/chunks/${prev.chunk_id}`)}
        >
          <ChevronLeft size={16} />
          前のチャンク
        </Button>
      ) : (
        <div />
      )}

      <div className="text-xs text-text-muted">
        {currentIdx + 1} / {neighbors.length}
      </div>

      {next ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/search/chunks/${next.chunk_id}`)}
        >
          次のチャンク
          <ChevronRight size={16} />
        </Button>
      ) : (
        <div />
      )}
    </motion.div>
  )
}
