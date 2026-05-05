import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { TagInput } from '@/components/notes/TagInput'
import { TipTapEditor } from '@/components/notes/TipTapEditor'
import { useCreateNote } from '@/hooks/useNotes'
import { useUIStore } from '@/stores/uiStore'

export default function NoteCreatePage() {
  const navigate = useNavigate()
  const createNote = useCreateNote()
  const addToast = useUIStore((s) => s.addToast)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [folder, setFolder] = useState('')
  const [tags, setTags] = useState<string[]>([])

  const handleCreate = async () => {
    if (!title.trim() || !content.trim()) {
      addToast({ type: 'warning', title: 'タイトルと内容を入力してください' })
      return
    }

    try {
      const res = await createNote.mutateAsync({
        title: title.trim(),
        content,
        folder: folder.trim() || undefined,
        tags: tags.length > 0 ? tags : undefined,
      })
      addToast({ type: 'success', title: 'ノートを作成しました' })
      navigate(`/notes/${res.data.document_id}`)
    } catch {
      addToast({ type: 'error', title: 'ノートの作成に失敗しました' })
    }
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
          <h1 className="text-2xl font-bold text-text-primary">新規ノート作成</h1>
          <p className="text-sm text-text-muted mt-1">新しいノートを作成します</p>
        </div>
      </div>

      <div className="space-y-4 mb-6">
        <Input
          label="タイトル"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="ノートのタイトル"
        />
        <Input
          label="フォルダ"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          placeholder="例: tech/rag"
        />
        <div>
          <label className="text-sm font-medium text-text-secondary mb-1 block">
            タグ
          </label>
          <TagInput tags={tags} onChange={setTags} />
        </div>
      </div>

      <div className="mb-4">
        <label className="text-sm font-medium text-text-secondary mb-2 block">
          内容 (Markdown)
        </label>
        <TipTapEditor content={content} onChange={setContent} />
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={handleCreate} loading={createNote.isPending}>
          作成
        </Button>
        <Button variant="ghost" onClick={() => navigate(-1)}>
          キャンセル
        </Button>
      </div>
    </motion.div>
  )
}
