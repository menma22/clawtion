import { useSearchStore } from '@/stores/searchStore'
import type { ChunkLevel } from '@/types/api'
import { cn } from '@/lib/utils'

export function SearchFilters() {
  const searchType = useSearchStore((s) => s.searchType)
  const setSearchType = useSearchStore((s) => s.setSearchType)
  const granularity = useSearchStore((s) => s.granularity)
  const setGranularity = useSearchStore((s) => s.setGranularity)
  const topK = useSearchStore((s) => s.topK)
  const setTopK = useSearchStore((s) => s.setTopK)

  const radioStyle = (active: boolean) => cn(
    'px-2.5 py-1 text-[11px] font-medium rounded-md cursor-pointer transition-colors',
    active ? 'bg-text text-app' : 'text-text-secondary hover:bg-hover',
  )

  const selectStyle = 'rounded-md border border-border bg-input px-2 py-1 text-[11px] text-text cursor-pointer outline-none'

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center rounded-lg border border-border p-0.5">
        {(['hybrid', 'semantic', 'keyword'] as const).map((type) => (
          <label key={type} className={radioStyle(searchType === type)}>
            <input type="radio" name="searchType" value={type} checked={searchType === type}
              onChange={() => setSearchType(type)} className="sr-only" />
            {type === 'hybrid' ? 'Hybrid' : type === 'semantic' ? 'Semantic' : 'Keyword'}
          </label>
        ))}
      </div>

      <select value={granularity} onChange={(e) => setGranularity(e.target.value as ChunkLevel)} className={selectStyle}>
        <option value="file">File</option>
        <option value="coarse">Coarse</option>
        <option value="fine">Fine</option>
        <option value="all">All</option>
      </select>

      <select value={topK} onChange={(e) => setTopK(Number(e.target.value))} className={selectStyle}>
        {[5, 10, 20, 30, 50].map((n) => <option key={n} value={n}>{n} results</option>)}
      </select>
    </div>
  )
}
