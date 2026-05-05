import { cn } from '@/lib/utils'

interface SpinnerProps { size?: 'sm' | 'md' | 'lg'; className?: string }

const sizeClasses = { sm: 'h-3.5 w-3.5', md: 'h-5 w-5', lg: 'h-8 w-8' }

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return (
    <div
      role="status" aria-label="Loading"
      className={cn(
        'animate-spin rounded-full border-2 border-current/20 border-t-current',
        sizeClasses[size],
        className,
      )}
    />
  )
}
