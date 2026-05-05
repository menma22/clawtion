import { useSearchStore } from '@/stores/searchStore'
import type { ChunkLevel } from '@/types/api'

export function SearchFilters() {
  const searchType = useSearchStore((s) => s.searchType)
  const setSearchType = useSearchStore((s) => s.setSearchType)
  const granularity = useSearchStore((s) => s.granularity)
  const setGranularity = useSearchStore((s) => s.setGranularity)
  const topK = useSearchStore((s) => s.topK)
  const setTopK = useSearchStore((s) => s.setTopK)

  return (
    <div className="flex flex-wrap items-center gap-4">
      <fieldset className="flex items-center gap-1">
        <legend className="text-xs font-medium text-text-muted mr-2">検索タイプ</legend>
        {(['hybrid', 'semantic', 'keyword'] as const).map((type) => (
          <label
            key={type}
            className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer transition-colors ${
              searchType === type
                ? 'bg-primary text-text-inverse'
                : 'bg-surface-input text-text-secondary hover:bg-border-default'
            }`}
          >
            <input
              type="radio"
              name="searchType"
              value={type}
              checked={searchType === type}
              onChange={() => setSearchType(type)}
              className="sr-only"
            />
            {type === 'hybrid' ? 'ハイブリッド' : type === 'semantic' ? 'セマンティック' : 'キーワード'}
          </label>
        ))}
      </fieldset>

      <div className="flex items-center gap-2">
        <label className="text-xs font-medium text-text-muted">粒度</label>
        <select
          value={granularity}
          onChange={(e) => setGranularity(e.target.value as ChunkLevel)}
          className="rounded-md border border-border-default bg-surface-input px-2 py-1.5 text-xs text-text-primary cursor-pointer"
        >
          <option value="file">ファイル</option>
          <option value="coarse">粗粒度</option>
          <option value="fine">細粒度</option>
          <option value="all">すべて</option>
        </select>
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs font-medium text-text-muted">件数</label>
        <select
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="rounded-md border border-border-default bg-surface-input px-2 py-1.5 text-xs text-text-primary cursor-pointer"
        >
          {[5, 10, 20, 30, 50].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
