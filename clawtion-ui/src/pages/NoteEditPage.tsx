import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { TagInput } from '@/components/notes/TagInput'
import { TipTapEditor } from '@/components/notes/TipTapEditor'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Spinner'
import { useNote, useUpdateNote, useDeleteNote } from '@/hooks/useNotes'
import { useUIStore } from '@/stores/uiStore'

export default function NoteEditPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const navigate = useNavigate()
  const { data, isLoading, isError } = useNote(documentId)
  const updateNote = useUpdateNote()
  const deleteNote = useDeleteNote()
  const addToast = useUIStore((s) => s.addToast)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [folder, setFolder] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [showDelete, setShowDelete] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (data) {
      setTitle(data.data.title)
      setContent(data.data.content)
      setFolder(data.data.folder_path.replace(/\/$/, ''))
      setTags(data.data.tags || [])
    }
  }, [data])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [content, title, folder, tags])

  if (isLoading) return <div className="flex items-center justify-center h-full"><Spinner size="lg" /></div>
  if (isError || !data) return (
    <div className="flex flex-col items-center justify-center h-full gap-3">
      <p className="text-sm text-text-secondary">ノートが見つかりません</p>
      <button onClick={() => navigate('/notes')} className="text-[13px] text-accent hover:underline cursor-pointer font-medium">ノート一覧に戻る</button>
    </div>
  )

  const handleSave = async () => {
    if (!documentId || saving) return
    setSaving(true)
    try {
      await updateNote.mutateAsync({ id: documentId, data: { content, title: title || undefined, folder: folder || undefined, tags: tags.length > 0 ? tags : undefined } })
      addToast({ type: 'success', title: '保存しました' })
    } catch { addToast({ type: 'error', title: '保存に失敗しました' }) }
    finally { setSaving(false) }
  }

  const handleDelete = async (permanent: boolean) => {
    if (!documentId) return
    try {
      await deleteNote.mutateAsync({ id: documentId, permanent })
      addToast({ type: 'success', title: permanent ? '完全に削除しました' : 'ゴミ箱に移動しました' })
      navigate('/notes')
    } catch { addToast({ type: 'error', title: '削除に失敗しました' }) }
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button onClick={() => navigate('/notes')} className="rounded-md p-1.5 text-text-tertiary hover:bg-hover hover:text-text-secondary transition-colors cursor-pointer shrink-0">
            <ArrowLeft size={18} />
          </button>
          <div className="flex-1 min-w-0">
            <Input value={title} onChange={(e) => setTitle(e.target.value)}
              className="text-[18px] font-bold border-none bg-transparent px-0 h-auto w-full" />
            <div className="flex items-center gap-2 mt-0.5">
              <Input value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="フォルダ" className="h-6 text-[11px] w-36" />
              <TagInput tags={tags} onChange={setTags} placeholder="タグ..." className="h-6 text-[11px]" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-4">
          <span className="text-[11px] text-text-tertiary mr-1">Ctrl+S</span>
          <button onClick={handleSave} disabled={saving}
            className="rounded-md bg-text px-3 py-1 text-[12px] font-medium text-app hover:bg-text/85 disabled:opacity-30 transition-colors cursor-pointer">
            {saving ? '保存中...' : '保存'}
          </button>
          <button onClick={() => setShowDelete(true)}
            className="rounded-md px-2 py-1 text-text-tertiary hover:text-danger hover:bg-danger-subtle transition-colors cursor-pointer">
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      <TipTapEditor content={content} onChange={setContent} />

      <Modal open={showDelete} onClose={() => setShowDelete(false)} title="ノートの削除">
        <p className="text-[13px] text-text-secondary mb-4">「{title}」を削除しますか？</p>
        <div className="flex gap-2">
          <button onClick={() => handleDelete(false)} disabled={deleteNote.isPending}
            className="rounded-md bg-input px-3 py-1.5 text-[12px] font-medium text-text hover:bg-hover transition-colors cursor-pointer">
            ゴミ箱に移動
          </button>
          <button onClick={() => handleDelete(true)} disabled={deleteNote.isPending}
            className="rounded-md bg-danger px-3 py-1.5 text-[12px] font-medium text-white hover:bg-danger-hover transition-colors cursor-pointer">
            完全に削除
          </button>
        </div>
      </Modal>
    </div>
  )
}
