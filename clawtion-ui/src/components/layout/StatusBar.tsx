import { useQueueStatus } from '@/hooks/useQueue'
import { useMetrics, useVersion } from '@/hooks/useSettings'
import { useSettingsStore } from '@/stores/settingsStore'
import { cn } from '@/lib/utils'

export function StatusBar() {
  const { data: queueData } = useQueueStatus()
  const { data: metricsData } = useMetrics()
  const { data: versionData } = useVersion()
  const vaultPath = useSettingsStore((s) => s.vaultPath)

  const queueStats = queueData?.data
  const metrics = metricsData?.data
  const version = versionData?.version ?? '0.1.0'

  // Show actual indexing state from metrics, not just queue
  const docCount = metrics?.total_documents ?? 0
  const chunkCount = metrics?.total_chunks ?? 0
  const queuePending = queueStats?.pending ?? 0
  const queueFailed = queueStats?.failed ?? 0
  const queueProcessing = queueStats?.processing ?? 0

  let indexingLabel: string
  let indexingColor: string
  if (queueFailed > 0) {
    indexingLabel = `${queueFailed} failed`
    indexingColor = 'bg-danger'
  } else if (queueProcessing > 0) {
    indexingLabel = 'Indexing...'
    indexingColor = 'bg-warning animate-pulse'
  } else if (queuePending > 0) {
    indexingLabel = `${queuePending} pending`
    indexingColor = 'bg-warning'
  } else if (chunkCount > 0) {
    indexingLabel = `${chunkCount} chunks indexed`
    indexingColor = 'bg-success'
  } else {
    indexingLabel = 'No index data'
    indexingColor = 'bg-text-tertiary'
  }

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border bg-sidebar px-3 text-[11px] text-text-tertiary select-none">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className={cn('h-1.5 w-1.5 rounded-full', indexingColor)} />
          <span>{indexingLabel}</span>
        </div>
        <span className="text-text-tertiary/60">{docCount} docs</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="max-w-48 truncate text-text-tertiary/70">{vaultPath}</span>
        <span className="text-text-tertiary/50">v{version}</span>
      </div>
    </footer>
  )
}
