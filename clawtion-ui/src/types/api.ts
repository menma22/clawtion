// ============================================================
// 共通型
// ============================================================

export interface APIResponse<T> {
  data: T
  meta: Record<string, unknown> & {
    execution_time_ms: number
  }
}

export interface APIError {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export type ChunkLevel = 'file' | 'coarse' | 'fine' | 'all'

export type QueueOperation = 'index' | 'reindex' | 'delete'

export type QueueStatus = 'pending' | 'processing' | 'partial' | 'completed' | 'failed'

// ============================================================
// 検索
// ============================================================

export interface SearchRequest {
  query: string
  granularity?: ChunkLevel
  top_k?: number
  metadata_filter?: {
    folder?: string
    tags?: string[]
    date_from?: string
    date_to?: string
    extension?: string
    namespace?: string | string[]
  }
}

export interface SearchResultItem {
  document_id: string
  chunk_id: string | null
  file_path: string
  title: string | null
  folder_path: string | null
  content: string
  content_with_context: string | null
  score: number
  chunk_level: ChunkLevel | null
  chunk_index: number | null
  heading_path: string | null
}

export interface SearchMeta {
  query: string
  total_results: number
  granularity: string
  search_type: 'semantic' | 'keyword' | 'hybrid'
  execution_time_ms: number
  cached: boolean
}

// ============================================================
// チャンク
// ============================================================

export interface ChunkItem {
  chunk_id: string
  document_id: string
  chunk_level: ChunkLevel
  chunk_index: number
  chunk_total: number
  parent_chunk_id: string | null
  heading_path: string | null
  content: string
  content_with_context: string | null
  token_count: number | null
  char_count: number | null
  created_at: string | null
}

// ============================================================
// ノート
// ============================================================

export interface CreateNoteRequest {
  title: string
  content: string
  folder?: string
  tags?: string[]
}

export interface UpdateNoteRequest {
  content: string
  title?: string
  folder?: string
  tags?: string[]
}

export interface NoteResponse {
  document_id: string
  title: string
  content: string
  folder_path: string
  tags: string[]
  file_path: string
  file_extension: string | null
  file_size_bytes: number | null
  total_chunks: number
  last_indexed_at: string | null
  created_at: string
  updated_at: string
}

export interface NoteListItem {
  document_id: string
  title: string
  folder_path: string
  tags: string[]
  file_path: string
  total_chunks: number
  created_at: string
  updated_at: string
}

export interface FolderItem {
  folder_path: string
  note_count: number
}

// ============================================================
// キュー
// ============================================================

export interface QueueStats {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
  cancelled: number
}

export interface QueueItem {
  queue_id: string
  document_id: string
  file_path: string
  operation: QueueOperation
  status: QueueStatus
  priority: number
  retry_count: number
  max_retries: number
  last_error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface SystemMetrics {
  total_documents: number
  total_chunks: number
  indexing_queue_pending: number
  indexing_queue_failed: number
  total_queue_items: number
  db_size_mb: number | null
  vault_path: string
  version: string
}

// ============================================================
// Health
// ============================================================

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  database: 'connected' | 'disconnected'
}

export interface VersionResponse {
  version: string
}
