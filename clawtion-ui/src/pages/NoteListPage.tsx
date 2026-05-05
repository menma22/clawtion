import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { NoteTable } from '@/components/notes/NoteTable'
import { useNotes } from '@/hooks/useNotes'
import { useNoteStore } from '@/stores/noteStore'

export default function NoteListPage() {
  const navigate = useNavigate()
  const folderFilter = useNoteStore((s) => s.folderFilter)
  const page = useNoteStore((s) => s.page)
  const pageSize = useNoteStore((s) => s.pageSize)
  const setPage = useNoteStore((s) => s.setPage)

  const { data, isLoading, isError, refetch } = useNotes(folderFilter, page, pageSize)
  const notes = data?.data ?? []

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-text tracking-tight">Notes</h1>
          <p className="text-[13px] text-text-secondary mt-0.5">
            {folderFilter || 'すべてのノート'}
            {notes.length > 0 && <span className="text-text-tertiary"> — {notes.length}件</span>}
          </p>
        </div>
        <button
          onClick={() => navigate('/notes/new')}
          className="inline-flex items-center gap-1.5 rounded-lg bg-text px-3.5 py-1.5 text-[13px] font-medium text-app hover:bg-text/85 transition-colors cursor-pointer"
        >
          <Plus size={16} />
          新規ノート
        </button>
      </div>

      <NoteTable notes={notes} isLoading={isLoading} isError={isError} onRetry={() => refetch()} />

      {notes.length > 0 && (
        <div className="mt-4 flex items-center justify-center gap-1">
          <button
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            className="rounded-md px-3 py-1 text-[12px] font-medium text-text-secondary hover:bg-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            ← 前
          </button>
          <span className="text-[12px] text-text-tertiary px-2">{page + 1}</span>
          <button
            disabled={notes.length < pageSize}
            onClick={() => setPage(page + 1)}
            className="rounded-md px-3 py-1 text-[12px] font-medium text-text-secondary hover:bg-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            次 →
          </button>
        </div>
      )}
    </div>
  )
}
