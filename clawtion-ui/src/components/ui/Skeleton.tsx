import { cn } from '@/lib/utils'

interface SkeletonProps { className?: string; variant?: 'text' | 'card' | 'circle' }

export function Skeleton({ className, variant = 'text' }: SkeletonProps) {
  return (
    <div
      role="status" aria-busy="true"
      className={cn(
        'animate-pulse rounded-md bg-hover',
        variant === 'text' && 'h-3.5 w-full',
        variant === 'card' && 'h-28 w-full rounded-lg',
        variant === 'circle' && 'h-8 w-8 rounded-full',
        className,
      )}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border p-5 space-y-3">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  )
}

export function SkeletonList({ count = 5 }: { count?: number }) {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3">
          <Skeleton variant="circle" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-2.5 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  )
}
