import { create } from 'zustand'

interface NoteStore {
  folderFilter: string | null
  page: number
  pageSize: number
  setFolderFilter: (folder: string | null) => void
  setPage: (page: number) => void
  setPageSize: (size: number) => void
}

export const useNoteStore = create<NoteStore>((set) => ({
  folderFilter: null,
  page: 0,
  pageSize: 50,
  setFolderFilter: (folder) => set({ folderFilter: folder, page: 0 }),
  setPage: (page) => set({ page }),
  setPageSize: (size) => set({ pageSize: size, page: 0 }),
}))
