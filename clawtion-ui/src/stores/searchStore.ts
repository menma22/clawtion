import { create } from 'zustand'
import type { ChunkLevel } from '@/types/api'

type SearchType = 'hybrid' | 'semantic' | 'keyword'

interface SearchStore {
  query: string
  searchType: SearchType
  granularity: ChunkLevel
  topK: number
  folderFilter: string | null
  setQuery: (q: string) => void
  setSearchType: (t: SearchType) => void
  setGranularity: (g: ChunkLevel) => void
  setTopK: (k: number) => void
  setFolderFilter: (f: string | null) => void
}

export const useSearchStore = create<SearchStore>((set) => ({
  query: '',
  searchType: 'hybrid',
  granularity: 'all',
  topK: 10,
  folderFilter: null,
  setQuery: (query) => set({ query }),
  setSearchType: (searchType) => set({ searchType }),
  setGranularity: (granularity) => set({ granularity }),
  setTopK: (topK) => set({ topK }),
  setFolderFilter: (folderFilter) => set({ folderFilter }),
}))
