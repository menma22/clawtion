import { describe, it, expect, beforeEach } from 'vitest'
import { useSearchStore } from '@/stores/searchStore'
import { useNoteStore } from '@/stores/noteStore'
import { useUIStore } from '@/stores/uiStore'
import { useQueueStore } from '@/stores/queueStore'

describe('SearchStore', () => {
  beforeEach(() => {
    useSearchStore.setState({
      query: '',
      searchType: 'hybrid',
      granularity: 'file',
      topK: 10,
      folderFilter: null,
    })
  })

  it('should update query', () => {
    useSearchStore.getState().setQuery('RAG')
    expect(useSearchStore.getState().query).toBe('RAG')
  })

  it('should change search type', () => {
    useSearchStore.getState().setSearchType('semantic')
    expect(useSearchStore.getState().searchType).toBe('semantic')
  })

  it('should change granularity', () => {
    useSearchStore.getState().setGranularity('coarse')
    expect(useSearchStore.getState().granularity).toBe('coarse')
  })

  it('should set topK', () => {
    useSearchStore.getState().setTopK(20)
    expect(useSearchStore.getState().topK).toBe(20)
  })
})

describe('NoteStore', () => {
  beforeEach(() => {
    useNoteStore.setState({
      folderFilter: null,
      page: 0,
      pageSize: 50,
    })
  })

  it('should set folder filter and reset page', () => {
    useNoteStore.getState().setPage(3)
    useNoteStore.getState().setFolderFilter('tech/')
    expect(useNoteStore.getState().folderFilter).toBe('tech/')
    expect(useNoteStore.getState().page).toBe(0)
  })

  it('should change page', () => {
    useNoteStore.getState().setPage(2)
    expect(useNoteStore.getState().page).toBe(2)
  })
})

describe('UIStore', () => {
  beforeEach(() => {
    useUIStore.setState({
      sidebarCollapsed: false,
      toasts: [],
    })
  })

  it('should toggle sidebar', () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
  })

  it('should add and remove toasts', () => {
    useUIStore.getState().addToast({ type: 'success', title: 'Test' })
    const toasts = useUIStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.type).toBe('success')

    useUIStore.getState().removeToast(toasts[0]!.id)
    expect(useUIStore.getState().toasts).toHaveLength(0)
  })
})

describe('QueueStore', () => {
  it('should change polling interval', () => {
    useQueueStore.getState().setPollingInterval(30_000)
    expect(useQueueStore.getState().pollingInterval).toBe(30_000)
  })
})
