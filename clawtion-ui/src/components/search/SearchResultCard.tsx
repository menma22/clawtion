import { motion } from 'framer-motion'
import { FileText, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { truncate } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import type { SearchResultItem } from '@/types/api'

interface SearchResultCardProps {
  result: SearchResultItem
  index: number
}

export function SearchResultCard({ result, index }: SearchResultCardProps) {
  const navigate = useNavigate()

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      whileHover={{ y: -1 }}
      className="group cursor-pointer rounded-lg border border-border-default bg-surface-card p-4 hover:border-primary/30 hover:shadow-card-hover transition-all"
      onClick={() => {
        if (result.chunk_id) {
          navigate(`/search/chunks/${result.chunk_id}`)
        } else if (result.document_id) {
          navigate(`/notes/${result.document_id}`)
        }
      }}
    >
      <div className="flex items-start gap-3">
        <FileText size={18} className="mt-0.5 text-text-muted shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-text-primary truncate">
              {result.title || result.file_path}
            </h3>
            <Badge
              variant={
                result.score >= 0.9 ? 'success' : result.score >= 0.7 ? 'warning' : 'info'
              }
              className="shrink-0"
            >
              スコア: {result.score.toFixed(2)}
            </Badge>
            {result.chunk_level && (
              <Badge variant="default" className="shrink-0">
                {result.chunk_level}
              </Badge>
            )}
          </div>
          <p className="text-xs text-text-muted mb-2">{result.file_path}</p>
          <p className="text-sm text-text-secondary leading-relaxed">
            {truncate(result.content, 250)}
          </p>
          {result.heading_path && (
            <p className="text-xs text-text-muted mt-1">
              セクション: {result.heading_path}
            </p>
          )}
        </div>
        <ChevronRight
          size={16}
          className="mt-2 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
        />
      </div>
    </motion.div>
  )
}
