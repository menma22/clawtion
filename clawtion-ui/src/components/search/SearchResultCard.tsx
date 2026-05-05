import { motion } from 'framer-motion'
import { FileText } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { truncate } from '@/lib/utils'
import type { SearchResultItem } from '@/types/api'

interface SearchResultCardProps { result: SearchResultItem; index: number }

export function SearchResultCard({ result, index }: SearchResultCardProps) {
  const navigate = useNavigate()

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.035, duration: 0.2 }}
      className="group cursor-pointer rounded-lg border border-border bg-card p-4 hover:border-accent/20 hover:shadow-sm transition-all"
      onClick={() => {
        if (result.chunk_id) navigate(`/search/chunks/${result.chunk_id}`)
        else if (result.document_id) navigate(`/notes/${result.document_id}`)
      }}
    >
      <div className="flex items-start gap-3">
        <FileText size={16} className="mt-0.5 text-text-tertiary shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="text-[14px] font-semibold text-text truncate">
              {result.title || result.file_path}
            </h3>
            <span className="text-[11px] font-medium text-text-tertiary shrink-0 tabular-nums">
              {result.score.toFixed(2)}
            </span>
            {result.chunk_level && (
              <span className="text-[10px] font-medium text-text-tertiary bg-hover rounded px-1.5 py-0.5 shrink-0">
                {result.chunk_level}
              </span>
            )}
          </div>
          <p className="text-[11px] text-text-tertiary mb-1.5">{result.file_path}</p>
          <p className="text-[13px] text-text-secondary leading-relaxed line-clamp-3">
            {truncate(result.content, 300)}
          </p>
        </div>
      </div>
    </motion.div>
  )
}
