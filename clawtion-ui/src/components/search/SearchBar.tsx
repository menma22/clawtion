import { useRef, useEffect, type KeyboardEvent } from 'react'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SearchBarProps {
  value: string; onChange: (v: string) => void; onSearch: () => void
  isLoading?: boolean; className?: string
}

export function SearchBar({ value, onChange, onSearch, isLoading, className }: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') onSearch()
  }

  return (
    <div className={cn('flex items-center gap-2 rounded-lg border border-border bg-input px-3 transition-all focus-within:border-accent/30 focus-within:ring-2 focus-within:ring-accent/10', className)}>
      <Search size={16} className="text-text-tertiary shrink-0" />
      <input
        ref={inputRef} type="text" value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="ノートを検索..."
        className="flex-1 bg-transparent py-2.5 text-[14px] text-text placeholder:text-text-tertiary outline-none"
      />
      {value && (
        <button onClick={() => onChange('')} className="p-0.5 text-text-tertiary hover:text-text-secondary cursor-pointer">
          <X size={16} />
        </button>
      )}
      <button
        onClick={onSearch} disabled={!value.trim() || isLoading}
        className="rounded-md bg-text px-3 py-1 text-[12px] font-medium text-app hover:bg-text/85 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
      >
        {isLoading ? '検索中...' : '検索'}
      </button>
    </div>
  )
}
