import { useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TagInputProps {
  tags: string[]
  onChange: (tags: string[]) => void
  className?: string
  placeholder?: string
}

export function TagInput({
  tags,
  onChange,
  className,
  placeholder = 'タグを追加...',
}: TagInputProps) {
  const [input, setInput] = useState('')

  const addTag = () => {
    const tag = input.trim().toLowerCase()
    if (tag && !tags.includes(tag)) {
      onChange([...tags, tag])
    }
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag()
    }
    if (e.key === 'Backspace' && !input && tags.length > 0) {
      onChange(tags.slice(0, -1))
    }
  }

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag))
  }

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-1.5 rounded-lg border border-border-default bg-surface-input px-3 py-2 min-h-10',
        className,
      )}
    >
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-md bg-surface-card px-2 py-0.5 text-xs font-medium text-text-primary border border-border-default"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tag)}
            className="text-text-muted hover:text-danger transition-colors cursor-pointer"
          >
            <X size={12} />
          </button>
        </span>
      ))}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => input && addTag()}
        placeholder={tags.length === 0 ? placeholder : ''}
        className="flex-1 min-w-20 bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none"
      />
    </div>
  )
}
