import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FileText } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { SkeletonList } from '@/components/ui/Skeleton'
import type { NoteListItem } from '@/types/api'

interface NoteTableProps {
  notes: NoteListItem[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function NoteTable({ notes, isLoading, isError, onRetry }: NoteTableProps) {
  const navigate = useNavigate()

  if (isLoading) return <SkeletonList count={8} />

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-text-muted mb-3">ノートの読み込みに失敗しました</p>
        <button
          onClick={onRetry}
          className="text-sm text-primary hover:underline cursor-pointer"
        >
          再試行
        </button>
      </div>
    )
  }

  if (!notes || notes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <FileText size={40} className="text-text-muted mb-3" />
        <p className="text-text-secondary font-medium mb-1">ノートがまだありません</p>
        <p className="text-sm text-text-muted">
          「+ 新規ノート」ボタンをクリックして最初のノートを作成しましょう
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border-default">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border-default bg-surface-sidebar">
            <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
              タイトル
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden sm:table-cell">
              フォルダ
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden md:table-cell">
              タグ
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase tracking-wider">
              更新日
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {notes.map((note, i) => (
            <motion.tr
              key={note.document_id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              onClick={() => navigate(`/notes/${note.document_id}`)}
              className="cursor-pointer hover:bg-surface-hover transition-colors"
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <FileText size={16} className="text-text-muted shrink-0" />
                  <span className="text-sm font-medium text-text-primary truncate max-w-60">
                    {note.title}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 hidden sm:table-cell">
                <span className="text-sm text-text-secondary">
                  {note.folder_path || '-'}
                </span>
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <div className="flex gap-1 flex-wrap">
                  {note.tags.slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="default" className="text-[10px]">
                      {tag}
                    </Badge>
                  ))}
                  {note.tags.length > 3 && (
                    <Badge variant="default" className="text-[10px]">
                      +{note.tags.length - 3}
                    </Badge>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-sm text-text-muted">
                  {formatRelativeTime(note.updated_at)}
                </span>
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
