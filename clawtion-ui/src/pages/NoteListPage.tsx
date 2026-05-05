import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
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
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">ノート</h1>
          <p className="text-sm text-text-muted mt-1">
            {folderFilter ? `フォルダ: ${folderFilter}` : 'すべてのノート'}
            {data?.meta && ` — ${notes.length}件`}
          </p>
        </div>
        <Button onClick={() => navigate('/notes/new')}>
          <Plus size={18} />
          新規ノート
        </Button>
      </div>

      <NoteTable
        notes={notes}
        isLoading={isLoading}
        isError={isError}
        onRetry={() => refetch()}
      />

      {/* Pagination */}
      {notes.length > 0 && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            前のページ
          </Button>
          <span className="text-sm text-text-muted">ページ {page + 1}</span>
          <Button
            variant="ghost"
            size="sm"
            disabled={notes.length < pageSize}
            onClick={() => setPage(page + 1)}
          >
            次のページ
          </Button>
        </div>
      )}
    </div>
  )
}
