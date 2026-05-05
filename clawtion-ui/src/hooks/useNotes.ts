import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { CreateNoteRequest, UpdateNoteRequest } from '@/types/api'

export function useNotes(folder?: string | null, page = 0, pageSize = 50) {
  return useQuery({
    queryKey: ['notes', folder, page, pageSize],
    queryFn: async () => {
      const res = await api.listNotes({
        folder: folder ?? undefined,
        limit: pageSize,
        offset: page * pageSize,
      })
      return res
    },
    staleTime: 30_000,
  })
}

export function useNote(id: string | undefined) {
  return useQuery({
    queryKey: ['note', id],
    queryFn: async () => {
      if (!id) throw new Error('No note ID')
      return api.getNote(id)
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function useCreateNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateNoteRequest) => api.createNote(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notes'] })
      qc.invalidateQueries({ queryKey: ['folders'] })
    },
  })
}

export function useUpdateNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateNoteRequest }) =>
      api.updateNote(id, data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['notes'] })
      qc.invalidateQueries({ queryKey: ['note', variables.id] })
    },
  })
}

export function useDeleteNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, permanent }: { id: string; permanent?: boolean }) =>
      api.deleteNote(id, permanent),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notes'] })
      qc.invalidateQueries({ queryKey: ['folders'] })
    },
  })
}
