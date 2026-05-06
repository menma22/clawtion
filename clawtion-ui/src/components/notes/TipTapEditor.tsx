import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import { useState, useEffect } from 'react'
import { Bold, Italic, Underline as UnderlineIcon, Strikethrough, Code, List, ListOrdered,
  Quote, Heading1, Heading2, Heading3, Undo2, Redo2, Eye, Edit3 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TipTapEditorProps {
  content: string; onChange: (html: string) => void
  placeholder?: string; editable?: boolean
}

export function TipTapEditor({ content, onChange, placeholder = '"\\" で始めて入力を開始...', editable = true }: TipTapEditorProps) {
  const [preview, setPreview] = useState(false)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ bulletList: { keepMarks: true }, orderedList: { keepMarks: true } }),
      Placeholder.configure({ placeholder }),
      Underline,
    ],
    content, editable,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  })

  // Sync editor content when content prop changes externally (e.g. API fetch completes)
  useEffect(() => {
    if (editor && content && editor.getHTML() !== content) {
      editor.commands.setContent(content, false)
    }
  }, [content, editor])

  if (!editor) {
    return <div className="flex items-center justify-center h-64 text-text-tertiary text-[13px]">読み込み中...</div>
  }

  const ToolBtn = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button
      type="button" onClick={onClick}
      className={cn('rounded p-1 transition-colors cursor-pointer',
        active ? 'bg-accent-subtle text-accent' : 'text-text-tertiary hover:bg-hover hover:text-text-secondary')}
    >
      {children}
    </button>
  )

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-card">
      {editable && (
        <div className="flex items-center gap-0.5 border-b border-border px-3 py-1.5 bg-sidebar/50 flex-wrap">
          <ToolBtn active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}><Bold size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}><UnderlineIcon size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()}><Strikethrough size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('code')} onClick={() => editor.chain().focus().toggleCode().run()}><Code size={15} /></ToolBtn>
          <div className="w-px h-4 bg-border mx-0.5" />
          <ToolBtn active={editor.isActive('heading', { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}><Heading1 size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('heading', { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}><Heading2 size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('heading', { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}><Heading3 size={15} /></ToolBtn>
          <div className="w-px h-4 bg-border mx-0.5" />
          <ToolBtn active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}><List size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()}><Quote size={15} /></ToolBtn>
          <ToolBtn active={editor.isActive('codeBlock')} onClick={() => editor.chain().focus().toggleCodeBlock().run()}><Code size={15} /></ToolBtn>
          <div className="w-px h-4 bg-border mx-0.5" />
          <ToolBtn active={false} onClick={() => editor.chain().focus().undo().run()}><Undo2 size={15} /></ToolBtn>
          <ToolBtn active={false} onClick={() => editor.chain().focus().redo().run()}><Redo2 size={15} /></ToolBtn>
          <div className="flex-1" />
          <div className="flex items-center rounded-md border border-border overflow-hidden">
            <button type="button" onClick={() => setPreview(false)}
              className={cn('px-2 py-0.5 text-[11px] font-medium transition-colors cursor-pointer', !preview ? 'bg-text text-app' : 'text-text-tertiary hover:bg-hover')}>
              <Edit3 size={12} className="inline mr-0.5" />Edit
            </button>
            <button type="button" onClick={() => setPreview(true)}
              className={cn('px-2 py-0.5 text-[11px] font-medium transition-colors cursor-pointer', preview ? 'bg-text text-app' : 'text-text-tertiary hover:bg-hover')}>
              <Eye size={12} className="inline mr-0.5" />Preview
            </button>
          </div>
        </div>
      )}
      <div className={cn(editable && 'min-h-[400px]')}>
        {preview ? (
          <div className="ProseMirror" dangerouslySetInnerHTML={{ __html: editor.getHTML() }} />
        ) : (
          <EditorContent editor={editor} />
        )}
      </div>
    </div>
  )
}
