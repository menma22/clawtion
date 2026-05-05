import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText } from 'lucide-react'
import { Spinner } from '@/components/ui/Spinner'
import { ChunkNavigator } from '@/components/search/ChunkNavigator'
import { useNeighborChunks } from '@/hooks/useSearch'

export default function ChunkDetailPage() {
  const { chunkId } = useParams<{ chunkId: string }>()
  const navigate = useNavigate()

  const { data, isLoading } = useNeighborChunks(chunkId, 2, 2)
  const neighbors = data?.data ?? []
  const current = neighbors.find((c) => c.chunk_id === chunkId)

  if (isLoading) return <div className="flex items-center justify-center h-full"><Spinner size="lg" /></div>

  if (!current) return (
    <div className="flex flex-col items-center justify-center h-full gap-3">
      <p className="text-sm text-text-secondary">チャンクが見つかりません</p>
      <button onClick={() => navigate(-1)} className="text-[13px] text-accent hover:underline cursor-pointer font-medium">戻る</button>
    </div>
  )

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="mb-5 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="rounded-md p-1.5 text-text-tertiary hover:bg-hover transition-colors cursor-pointer">
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-[18px] font-bold text-text">{current.heading_path || 'Chunk Detail'}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="rounded bg-accent-subtle px-1.5 py-0.5 text-[10px] font-medium text-accent">{current.chunk_level}</span>
            <span className="text-[11px] text-text-tertiary">chunk {current.chunk_index + 1}/{current.chunk_total}</span>
          </div>
        </div>
        <div className="flex-1" />
        <button onClick={() => navigate(`/notes/${current.document_id}`)}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium text-text-secondary hover:bg-hover transition-colors cursor-pointer">
          <FileText size={14} />ノート全体を開く
        </button>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <div className="text-[15px] text-text leading-relaxed whitespace-pre-wrap">{current.content}</div>
      </div>

      {neighbors.length > 1 && (
        <ChunkNavigator currentChunkId={chunkId!} neighbors={neighbors} documentId={current.document_id} />
      )}
    </div>
  )
}
