import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch as unknown as typeof fetch

// We need to re-import after mocking
describe('ApiClient', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: { execution_time_ms: 5 } }),
    })
  })

  it('should call listNotes with correct URL', async () => {
    const { api } = await import('@/lib/api')
    await api.listNotes({ folder: 'tech/', limit: 10 })
    const url = mockFetch.mock.calls[0]![0] as string
    expect(url).toContain('/api/v1/notes')
    expect(url).toContain('folder=tech%2F')
    expect(url).toContain('limit=10')
  })

  it('should call search with POST body', async () => {
    const { api } = await import('@/lib/api')
    await api.search('hybrid', { query: 'test', top_k: 5 })
    const call = mockFetch.mock.calls[0]!
    expect(call[0]).toContain('/search/hybrid')
    expect(call[1]?.method).toBe('POST')
    const body = JSON.parse(call[1]?.body as string)
    expect(body.query).toBe('test')
  })

  it('should throw ApiRequestError on error response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: 'NOT_FOUND', message: 'Not found' } }),
    })
    const { api, ApiRequestError } = await import('@/lib/api')
    await expect(api.getNote('bad-id')).rejects.toThrow(ApiRequestError)
  })
})
