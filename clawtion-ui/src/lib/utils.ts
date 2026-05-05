import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'たった今'
  if (diffMin < 60) return `${diffMin}分前`
  if (diffHour < 24) return `${diffHour}時間前`
  if (diffDay < 30) return `${diffDay}日前`
  return formatDate(iso)
}

export function truncate(str: string, max: number): string {
  if (str.length <= max) return str
  return str.slice(0, max) + '...'
}

export function highlightScore(score: number): string {
  if (score >= 0.9) return 'text-success'
  if (score >= 0.7) return 'text-warning'
  if (score >= 0.5) return 'text-text-secondary'
  return 'text-text-muted'
}

export function queueStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-success'
    case 'processing':
      return 'bg-primary animate-pulse'
    case 'pending':
      return 'bg-warning'
    case 'failed':
      return 'bg-danger'
    default:
      return 'bg-text-muted'
  }
}
