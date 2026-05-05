import { useState } from 'react'
import { motion } from 'framer-motion'
import { SearchBar } from '@/components/search/SearchBar'
import { SearchResultCard } from '@/components/search/SearchResultCard'
import { SearchFilters } from '@/components/search/SearchFilters'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useSearch } from '@/hooks/useSearch'
import { useSearchStore } from '@/stores/searchStore'
import { SearchIcon } from 'lucide-react'

export default function SearchPage() {
  const query = useSearchStore((s) => s.query)
  const setQuery = useSearchStore((s) => s.setQuery)
  const searchType = useSearchStore((s) => s.searchType)
  const granularity = useSearchStore((s) => s.granularity)
  const topK = useSearchStore((s) => s.topK)
  const folderFilter = useSearchStore((s) => s.folderFilter)

  const [searchRequest, setSearchRequest] = useState<{
    query: string
    granularity: typeof granularity
    top_k: number
    metadata_filter?: { folder?: string }
  } | null>(null)

  const { data, isLoading } = useSearch(searchType, searchRequest)
  const results = data?.data ?? []
  const meta = data?.meta as Record<string, unknown> | undefined

  const handleSearch = () => {
    if (!query.trim()) return
    setSearchRequest({
      query: query.trim(),
      granularity,
      top_k: topK,
      metadata_filter: folderFilter ? { folder: folderFilter } : undefined,
    })
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-text-primary mb-4">検索</h1>
        <SearchBar
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          isLoading={isLoading}
        />
        <div className="mt-3">
          <SearchFilters />
        </div>
      </motion.div>

      {/* Results meta */}
      {meta && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-6 mb-3 text-sm text-text-muted"
        >
          {String(meta.total_results)}件の結果 ({String(meta.execution_time_ms)}ms) — {searchType}
        </motion.div>
      )}

      {/* Results */}
      <div className="mt-3 space-y-3">
        {isLoading && (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        )}

        {!isLoading &&
          results.map((result, i) => (
            <SearchResultCard key={result.chunk_id || i} result={result} index={i} />
          ))}

        {!isLoading && searchRequest && results.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-16 text-center"
          >
            <SearchIcon size={40} className="text-text-muted mb-3" />
            <p className="text-text-secondary font-medium mb-1">検索結果がありません</p>
            <p className="text-sm text-text-muted">
              別のキーワードや条件で検索してみてください
            </p>
          </motion.div>
        )}

        {!searchRequest && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-16 text-center"
          >
            <SearchIcon size={40} className="text-text-muted mb-3" />
            <p className="text-text-secondary font-medium mb-1">検索クエリを入力してください</p>
            <p className="text-sm text-text-muted">
              ハイブリッド検索で、あなたのナレッジベースを探索します
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}
