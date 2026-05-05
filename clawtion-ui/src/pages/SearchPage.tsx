import { useState } from 'react'
import { SearchIcon } from 'lucide-react'
import { SearchBar } from '@/components/search/SearchBar'
import { SearchResultCard } from '@/components/search/SearchResultCard'
import { SearchFilters } from '@/components/search/SearchFilters'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useSearch } from '@/hooks/useSearch'
import { useSearchStore } from '@/stores/searchStore'

export default function SearchPage() {
  const query = useSearchStore((s) => s.query)
  const setQuery = useSearchStore((s) => s.setQuery)
  const searchType = useSearchStore((s) => s.searchType)
  const granularity = useSearchStore((s) => s.granularity)
  const topK = useSearchStore((s) => s.topK)
  const folderFilter = useSearchStore((s) => s.folderFilter)

  const [searchRequest, setSearchRequest] = useState<{
    query: string; granularity: typeof granularity; top_k: number
    metadata_filter?: { folder?: string }
  } | null>(null)

  const { data, isLoading } = useSearch(searchType, searchRequest)
  const results = data?.data ?? []
  const meta = data?.meta as Record<string, unknown> | undefined

  const handleSearch = () => {
    if (!query.trim()) return
    setSearchRequest({ query: query.trim(), granularity, top_k: topK, metadata_filter: folderFilter ? { folder: folderFilter } : undefined })
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <h1 className="text-[22px] font-bold text-text tracking-tight mb-5">Search</h1>

      <SearchBar value={query} onChange={setQuery} onSearch={handleSearch} isLoading={isLoading} />
      <div className="mt-3"><SearchFilters /></div>

      {meta && (
        <div className="mt-5 mb-1 text-[12px] text-text-tertiary">
          {String(meta.total_results)}件 ({String(meta.execution_time_ms)}ms)
        </div>
      )}

      <div className="mt-3 space-y-2">
        {isLoading && <><SkeletonCard /><SkeletonCard /><SkeletonCard /></>}

        {!isLoading && searchRequest && results.map((r, i) => (
          <SearchResultCard key={r.chunk_id || i} result={r} index={i} />
        ))}

        {!isLoading && searchRequest && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-hover mb-4">
              <SearchIcon size={22} className="text-text-tertiary" />
            </div>
            <h3 className="text-[15px] font-semibold text-text mb-1">結果が見つかりません</h3>
            <p className="text-[13px] text-text-secondary">別のキーワードで検索してみてください</p>
          </div>
        )}

        {!searchRequest && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-hover mb-4">
              <SearchIcon size={22} className="text-text-tertiary" />
            </div>
            <h3 className="text-[15px] font-semibold text-text mb-1">ナレッジベースを検索</h3>
            <p className="text-[13px] text-text-secondary">ハイブリッド検索で、あなたのノートを探索します</p>
          </div>
        )}
      </div>
    </div>
  )
}
