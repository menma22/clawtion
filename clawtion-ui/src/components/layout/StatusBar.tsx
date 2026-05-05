import { useQueueStatus } from '@/hooks/useQueue'
import { useVersion } from '@/hooks/useSettings'
import { useSettingsStore } from '@/stores/settingsStore'
import { cn } from '@/lib/utils'

export function StatusBar() {
  const { data: queueData } = useQueueStatus()
  const { data: versionData } = useVersion()
  const vaultPath = useSettingsStore((s) => s.vaultPath)

  const stats = queueData?.data
  const version = versionData?.version ?? '0.1.0'

  let indexingLabel = 'Idle'
  let indexingColor = 'bg-success'
  if (stats) {
    if (stats.failed > 0) { indexingLabel = `${stats.failed} failed`; indexingColor = 'bg-danger' }
    else if (stats.processing > 0) { indexingLabel = 'Indexing...'; indexingColor = 'bg-warning animate-pulse' }
    else if (stats.pending > 0) { indexingLabel = `${stats.pending} pending`; indexingColor = 'bg-warning' }
    else { indexingLabel = `${stats.completed} indexed` }
  }

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border bg-sidebar px-3 text-[11px] text-text-tertiary select-none">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className={cn('h-1.5 w-1.5 rounded-full', indexingColor)} />
          <span>{indexingLabel}</span>
        </div>
        {stats && (
          <span className="text-text-tertiary/60">{stats.total} docs</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="max-w-48 truncate text-text-tertiary/70">{vaultPath}</span>
        <span className="text-text-tertiary/50">v{version}</span>
      </div>
    </footer>
  )
}
