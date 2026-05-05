import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Save, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
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
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (data) {
      setTitle(data.data.title)
      setContent(data.data.content)
      setFolder(data.data.folder_path.replace(/\/$/, ''))
      setTags(data.data.tags || [])
    }
  }, [data])

  // Ctrl+S shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [content, title, folder, tags])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-text-muted">ノートが見つかりません</p>
        <Button variant="ghost" onClick={() => navigate('/notes')}>
          ノート一覧に戻る
        </Button>
      </div>
    )
  }

  const handleSave = async () => {
    if (!documentId || saving) return
    setSaving(true)
    try {
      await updateNote.mutateAsync({
        id: documentId,
        data: {
          content,
          title: title || undefined,
          folder: folder || undefined,
          tags: tags.length > 0 ? tags : undefined,
        },
      })
      addToast({ type: 'success', title: '保存しました' })
    } catch {
      addToast({ type: 'error', title: '保存に失敗しました' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (permanent: boolean) => {
    if (!documentId) return
    try {
      await deleteNote.mutateAsync({ id: documentId, permanent })
      addToast({ type: 'success', title: permanent ? '完全に削除しました' : 'ゴミ箱に移動しました' })
      navigate('/notes')
    } catch {
      addToast({ type: 'error', title: '削除に失敗しました' })
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-5xl mx-auto p-6"
    >
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/notes')}
            className="p-2 rounded-lg text-text-muted hover:bg-surface-input hover:text-text-secondary transition-colors cursor-pointer"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="タイトル"
              className="text-lg font-bold border-none bg-transparent px-0 h-auto text-2xl"
            />
            <div className="flex items-center gap-3 mt-1">
              <Input
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder="フォルダ"
                className="text-xs h-7 w-48"
              />
              <TagInput
                tags={tags}
                onChange={setTags}
                placeholder="タグ追加..."
                className="h-7 text-xs"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={handleSave} loading={saving} size="sm">
            <Save size={16} />
            保存
          </Button>
          <Button variant="danger" size="sm" onClick={() => setShowDeleteModal(true)}>
            <Trash2 size={16} />
            削除
          </Button>
        </div>
      </div>

      {/* Editor */}
      <TipTapEditor content={content} onChange={setContent} />

      {/* Delete modal */}
      <Modal
        open={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="ノートの削除"
      >
        <p className="text-sm text-text-secondary mb-4">
          「{title}」を削除しますか？
        </p>
        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={() => handleDelete(false)}
            loading={deleteNote.isPending}
          >
            ゴミ箱に移動
          </Button>
          <Button
            variant="danger"
            onClick={() => handleDelete(true)}
            loading={deleteNote.isPending}
          >
            完全に削除
          </Button>
        </div>
      </Modal>
    </motion.div>
  )
}
