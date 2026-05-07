import { create } from 'zustand'

type SearchType = 'hybrid' | 'semantic' | 'keyword'
type LevelKey = 'file' | 'coarse' | 'fine'

interface SearchStore {
  query: string
  searchType: SearchType
  enabledLevels: Record<LevelKey, boolean>
  topK: number
  folderFilter: string | null
  setQuery: (q: string) => void
  setSearchType: (t: SearchType) => void
  toggleLevel: (level: LevelKey) => void
  setTopK: (k: number) => void
  setFolderFilter: (f: string | null) => void
  /** 有効な粒度をカンマ区切り文字列で返す（APIリクエスト用） */
  getGranularity: () => string
}

export const useSearchStore = create<SearchStore>((set, get) => ({
  query: '',
  searchType: 'hybrid',
  enabledLevels: { file: true, coarse: true, fine: true },
  topK: 10,
  folderFilter: null,
  setQuery: (query) => set({ query }),
  setSearchType: (searchType) => set({ searchType }),
  toggleLevel: (level) =>
    set((s) => ({
      enabledLevels: { ...s.enabledLevels, [level]: !s.enabledLevels[level] },
    })),
  setTopK: (topK) => set({ topK }),
  setFolderFilter: (folderFilter) => set({ folderFilter }),
  getGranularity: () => {
    const levels = get().enabledLevels
    const enabled = (Object.keys(levels) as LevelKey[]).filter((k) => levels[k])
    return enabled.length > 0 ? enabled.join(',') : 'file'
  },
}))
