import { useState, type KeyboardEvent, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SearchBarProps {
  value: string
  onChange: (v: string) => void
  onSearch: () => void
  isLoading?: boolean
  className?: string
}

export function SearchBar({
  value,
  onChange,
  onSearch,
  isLoading,
  className,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') onSearch()
  }

  return (
    <motion.div
      animate={focused ? { scale: 1.01 } : { scale: 1 }}
      className={cn(
        'flex items-center gap-2 rounded-xl border-2 bg-surface-input transition-colors',
        focused ? 'border-primary shadow-sm shadow-primary/10' : 'border-transparent',
        className,
      )}
    >
      <Search size={20} className="ml-4 text-text-muted shrink-0" />
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="ノートを検索... (Enterで実行)"
        className="flex-1 bg-transparent py-3 text-base text-text-primary placeholder:text-text-muted outline-none"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="p-1 text-text-muted hover:text-text-secondary cursor-pointer"
        >
          <X size={18} />
        </button>
      )}
      <button
        onClick={onSearch}
        disabled={!value.trim() || isLoading}
        className="mr-2 rounded-lg bg-primary px-4 py-1.5 text-sm font-medium text-text-inverse hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
      >
        {isLoading ? '検索中...' : '検索'}
      </button>
    </motion.div>
  )
}
