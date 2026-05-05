import { useQueueStatus } from '@/hooks/useQueue'
import { useVersion } from '@/hooks/useSettings'
import { useSettingsStore } from '@/stores/settingsStore'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

export function StatusBar() {
  const { data: queueData } = useQueueStatus()
  const { data: versionData } = useVersion()
  const vaultPath = useSettingsStore((s) => s.vaultPath)

  const stats = queueData?.data
  const version = versionData?.version ?? '0.1.0'

  let indexingStatus: 'idle' | 'processing' | 'error' = 'idle'
  if (stats) {
    if (stats.failed > 0) indexingStatus = 'error'
    else if (stats.processing > 0 || stats.pending > 0) indexingStatus = 'processing'
  }

  return (
    <footer className="flex h-8 shrink-0 items-center justify-between border-t border-border-default bg-surface-sidebar px-4 text-[11px] text-text-muted">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div
            className={cn(
              'h-1.5 w-1.5 rounded-full',
              indexingStatus === 'idle' && 'bg-success',
              indexingStatus === 'processing' && 'bg-warning animate-pulse',
              indexingStatus === 'error' && 'bg-danger',
            )}
          />
          <span>
            Indexing:
            {indexingStatus === 'idle' && ' 完了'}
            {indexingStatus === 'processing' &&
              ` 処理中 (${stats?.pending ?? 0} pending)`}
            {indexingStatus === 'error' && ` エラー (${stats?.failed ?? 0} failed)`}
          </span>
        </div>
        {stats && (
          <span>
            ドキュメント: {stats.completed}/{stats.total}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="truncate max-w-60">{vaultPath}</span>
        <Badge variant="default" className="text-[10px]">v{version}</Badge>
      </div>
    </footer>
  )
}
