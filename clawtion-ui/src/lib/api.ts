import type {
  APIResponse,
  ChunkItem,
  CreateNoteRequest,
  FolderItem,
  HealthResponse,
  NoteListItem,
  NoteResponse,
  QueueItem,
  QueueStats,
  SearchRequest,
  SearchResultItem,
  SystemMetrics,
  UpdateNoteRequest,
  VersionResponse,
} from '@/types/api'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

export class ApiRequestError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

class ApiClient {
  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    params?: Record<string, string | number | boolean | undefined>,
  ): Promise<APIResponse<T>> {
    const url = new URL(`${BASE_URL}${path}`)

    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) {
          url.searchParams.set(k, String(v))
        }
      }
    }

    const res = await fetch(url.toString(), {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({
        error: { code: 'NETWORK_ERROR', message: res.statusText },
      }))
      throw new ApiRequestError(
        err.error?.code ?? 'UNKNOWN',
        err.error?.message ?? res.statusText,
        res.status,
      )
    }

    return res.json()
  }

  // ---- ノート ----
  listNotes(params?: { folder?: string; limit?: number; offset?: number }) {
    return this.request<NoteListItem[]>('GET', '/notes', undefined, params)
  }

  getNote(id: string) {
    return this.request<NoteResponse>('GET', `/notes/${id}`)
  }

  createNote(data: CreateNoteRequest) {
    return this.request<NoteResponse>('POST', '/notes', data)
  }

  updateNote(id: string, data: UpdateNoteRequest) {
    return this.request<NoteResponse>('PUT', `/notes/${id}`, data)
  }

  deleteNote(id: string, permanent = false) {
    return this.request<{ document_id: string; deleted: boolean; permanent: boolean }>(
      'DELETE',
      `/notes/${id}`,
      undefined,
      { permanent },
    )
  }

  // ---- 検索 ----
  search(type: 'semantic' | 'keyword' | 'hybrid', data: SearchRequest) {
    return this.request<SearchResultItem[]>('POST', `/search/${type}`, data)
  }

  // ---- チャンク ----
  getFileChunks(documentId: string, level = 'file') {
    return this.request<ChunkItem[]>('GET', `/chunks/${documentId}/all`, undefined, { level })
  }

  getNeighborChunks(chunkId: string, before = 1, after = 1) {
    return this.request<ChunkItem[]>('GET', `/chunks/${chunkId}/neighbors`, undefined, {
      before,
      after,
    })
  }

  getParentChunk(chunkId: string) {
    return this.request<ChunkItem | null>('GET', `/chunks/${chunkId}/parent`)
  }

  // ---- キュー ----
  getQueueStatus() {
    return this.request<QueueStats>('GET', '/queue/status')
  }

  getQueuePending(limit = 50, offset = 0) {
    return this.request<QueueItem[]>('GET', '/queue/pending', undefined, { limit, offset })
  }

  getQueueFailed(limit = 50, offset = 0) {
    return this.request<QueueItem[]>('GET', '/queue/failed', undefined, { limit, offset })
  }

  processQueue() {
    return this.request<{ triggered: boolean }>('POST', '/queue/process')
  }

  retryQueueItem(queueId: string) {
    return this.request<QueueItem>('POST', `/queue/retry/${queueId}`)
  }

  clearFailedQueue() {
    return this.request<{ removed: number }>('POST', '/queue/clear-failed')
  }

  // ---- フォルダ ----
  getFolders() {
    return this.request<FolderItem[]>('GET', '/folders')
  }

  // ---- システム ----
  getMetrics() {
    return this.request<SystemMetrics>('GET', '/metrics')
  }

  getHealth() {
    return fetch(`${BASE_URL.replace('/api/v1', '')}/health`).then(
      (r) => r.json() as Promise<HealthResponse>,
    )
  }

  getVersion() {
    return fetch(`${BASE_URL.replace('/api/v1', '')}/version`).then(
      (r) => r.json() as Promise<VersionResponse>,
    )
  }
}

export const api = new ApiClient()
