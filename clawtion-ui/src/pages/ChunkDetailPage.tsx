import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, FileText } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { ChunkNavigator } from '@/components/search/ChunkNavigator'
import { useNeighborChunks } from '@/hooks/useSearch'

export default function ChunkDetailPage() {
  const { chunkId } = useParams<{ chunkId: string }>()
  const navigate = useNavigate()

  const { data, isLoading } = useNeighborChunks(chunkId, 2, 2)
  const neighbors = data?.data ?? []
  const current = neighbors.find((c) => c.chunk_id === chunkId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!current) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-text-muted">チャンクが見つかりません</p>
        <Button variant="ghost" onClick={() => navigate(-1)}>
          戻る
        </Button>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto p-6"
    >
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg text-text-muted hover:bg-surface-input hover:text-text-secondary transition-colors cursor-pointer"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-xl font-bold text-text-primary">
            {current.heading_path || current.document_id}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="info">{current.chunk_level}</Badge>
            <span className="text-xs text-text-muted">
              チャンク {current.chunk_index + 1} / {current.chunk_total}
            </span>
            {current.token_count && (
              <span className="text-xs text-text-muted">
                {current.token_count} tokens
              </span>
            )}
          </div>
        </div>
        <div className="flex-1" />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/notes/${current.document_id}`)}
        >
          <FileText size={16} />
          ノート全体を開く
        </Button>
      </div>

      {/* Content */}
      <div className="rounded-lg border border-border-default bg-surface-card p-6">
        <div className="prose prose-slate max-w-none text-text-primary whitespace-pre-wrap">
          {current.content}
        </div>
      </div>

      {/* Context */}
      {current.content_with_context && (
        <div className="mt-4 rounded-lg border border-border-default bg-surface-sidebar p-4">
          <h3 className="text-xs font-medium text-text-muted uppercase mb-2">コンテキスト</h3>
          <p className="text-sm text-text-secondary whitespace-pre-wrap">
            {current.content_with_context}
          </p>
        </div>
      )}

      {/* Navigation */}
      {neighbors.length > 1 && (
        <ChunkNavigator
          currentChunkId={chunkId!}
          neighbors={neighbors}
          documentId={current.document_id}
        />
      )}
    </motion.div>
  )
}
