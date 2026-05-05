import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SearchBar } from '@/components/search/SearchBar'

describe('SearchBar', () => {
  it('renders with placeholder', () => {
    render(<SearchBar value="" onChange={() => {}} onSearch={() => {}} />)
    expect(screen.getByPlaceholderText(/検索/)).toBeInTheDocument()
  })

  it('calls onSearch when Enter is pressed', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    render(<SearchBar value="RAG" onChange={() => {}} onSearch={onSearch} />)

    const input = screen.getByPlaceholderText(/検索/)
    await user.type(input, '{enter}')
    expect(onSearch).toHaveBeenCalled()
  })

  it('calls onSearch when button is clicked', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    render(<SearchBar value="RAG" onChange={() => {}} onSearch={onSearch} />)

    await user.click(screen.getByText('検索'))
    expect(onSearch).toHaveBeenCalled()
  })

  it('shows loading state', () => {
    render(<SearchBar value="test" onChange={() => {}} onSearch={() => {}} isLoading />)
    expect(screen.getByText('検索中...')).toBeInTheDocument()
  })
})
