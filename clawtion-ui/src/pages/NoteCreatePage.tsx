import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
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
    if (!title.trim()) { addToast({ type: 'warning', title: 'タイトルを入力してください' }); return }
    console.log('[NoteCreate] Creating note:', { title: title.trim(), contentLength: content.length, folder, tags })
    try {
      const res = await createNote.mutateAsync({
        title: title.trim(), content, folder: folder.trim() || undefined,
        tags: tags.length > 0 ? tags : undefined,
      })
      console.log('[NoteCreate] Success:', res)
      addToast({ type: 'success', title: 'ノートを作成しました' })
      navigate(`/notes/${res.data.document_id}`)
    } catch (err: any) {
      console.error('[NoteCreate] Error:', err)
      const msg = err?.message || err?.code || '不明なエラー'
      addToast({ type: 'error', title: '作成に失敗しました', message: msg })
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <div className="mb-6 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="rounded-md p-1.5 text-text-tertiary hover:bg-hover hover:text-text-secondary transition-colors cursor-pointer">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <Input
            value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="ノートタイトル"
            className="text-[20px] font-bold border-none bg-transparent px-0 h-auto w-full"
          />
          <div className="flex items-center gap-2 mt-1">
            <Input value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="フォルダ (任意)" className="h-7 text-[12px] w-48" />
            <TagInput tags={tags} onChange={setTags} placeholder="タグ..." className="h-7 text-[12px]" />
          </div>
        </div>
      </div>

      <TipTapEditor content={content} onChange={setContent} />

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={handleCreate}
          disabled={createNote.isPending || !title.trim()}
          className="rounded-lg bg-text px-4 py-1.5 text-[13px] font-medium text-app hover:bg-text/85 disabled:opacity-30 transition-colors cursor-pointer"
        >
          {createNote.isPending ? '作成中...' : '作成'}
        </button>
        <button onClick={() => navigate(-1)} className="rounded-lg px-4 py-1.5 text-[13px] font-medium text-text-secondary hover:bg-hover transition-colors cursor-pointer">
          キャンセル
        </button>
      </div>
    </div>
  )
}
