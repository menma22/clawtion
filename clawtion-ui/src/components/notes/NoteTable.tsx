import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FileText, Plus } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
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
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-sm text-text-secondary mb-3">ノートの読み込みに失敗しました</p>
        <button onClick={onRetry} className="text-[13px] text-accent hover:underline cursor-pointer font-medium">
          再試行
        </button>
      </div>
    )
  }

  if (!notes || notes.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center py-24 text-center"
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-hover mb-4">
          <FileText size={22} className="text-text-tertiary" />
        </div>
        <h3 className="text-[15px] font-semibold text-text mb-1">ノートがまだありません</h3>
        <p className="text-[13px] text-text-secondary mb-4 max-w-sm">
          新しいノートを作成して、あなたのナレッジベースを構築しましょう。
        </p>
        <button
          onClick={() => navigate('/notes/new')}
          className="inline-flex items-center gap-1.5 rounded-md bg-text px-3.5 py-1.5 text-[13px] font-medium text-app hover:bg-text/85 transition-colors cursor-pointer"
        >
          <Plus size={15} />
          最初のノートを作成
        </button>
      </motion.div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-sidebar/50">
            <th className="px-4 py-2.5 text-left text-[11px] font-medium text-text-tertiary uppercase tracking-wider">タイトル</th>
            <th className="px-4 py-2.5 text-left text-[11px] font-medium text-text-tertiary uppercase tracking-wider hidden sm:table-cell">フォルダ</th>
            <th className="px-4 py-2.5 text-left text-[11px] font-medium text-text-tertiary uppercase tracking-wider hidden md:table-cell">タグ</th>
            <th className="px-4 py-2.5 text-right text-[11px] font-medium text-text-tertiary uppercase tracking-wider">更新日</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {notes.map((note, i) => (
            <motion.tr
              key={note.document_id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.02 }}
              onClick={() => navigate(`/notes/${note.document_id}`)}
              className="cursor-pointer hover:bg-hover/50 transition-colors group"
            >
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2.5">
                  <FileText size={15} className="text-text-tertiary shrink-0 group-hover:text-accent transition-colors" />
                  <span className="text-[14px] font-medium text-text truncate max-w-72">{note.title}</span>
                </div>
              </td>
              <td className="px-4 py-2.5 hidden sm:table-cell">
                <span className="text-[12px] text-text-tertiary">{note.folder_path || '—'}</span>
              </td>
              <td className="px-4 py-2.5 hidden md:table-cell">
                <div className="flex gap-1 flex-wrap">
                  {note.tags.slice(0, 3).map((tag) => (
                    <span key={tag} className="inline-flex rounded-md bg-hover px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary">
                      {tag}
                    </span>
                  ))}
                </div>
              </td>
              <td className="px-4 py-2.5 text-right">
                <span className="text-[12px] text-text-tertiary tabular-nums">{formatRelativeTime(note.updated_at)}</span>
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
