import { RotateCw, Play, Trash2 } from 'lucide-react'
import { Spinner } from '@/components/ui/Spinner'
import { useQueueStatus, usePendingJobs, useFailedJobs, useProcessQueue, useRetryJob, useClearFailed } from '@/hooks/useQueue'
import { useUIStore } from '@/stores/uiStore'
import { formatRelativeTime } from '@/lib/utils'

export default function QueuePage() {
  const { data: statsData, isLoading: statsLoading } = useQueueStatus()
  const { data: pendingData, isLoading: pendingLoading } = usePendingJobs()
  const { data: failedData, isLoading: failedLoading } = useFailedJobs()
  const processQueue = useProcessQueue()
  const retryJob = useRetryJob()
  const clearFailed = useClearFailed()
  const addToast = useUIStore((s) => s.addToast)

  const stats = statsData?.data
  const pending = pendingData?.data ?? []
  const failed = failedData?.data ?? []

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-bold text-text tracking-tight">Queue</h1>
          <p className="text-[13px] text-text-secondary mt-0.5">Indexing ジョブの状態</p>
        </div>
        <button onClick={() => processQueue.mutate()} disabled={processQueue.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-text px-3.5 py-1.5 text-[13px] font-medium text-app hover:bg-text/85 disabled:opacity-30 transition-colors cursor-pointer">
          <Play size={14} />処理実行
        </button>
      </div>

      {statsLoading ? <div className="flex justify-center py-12"><Spinner /></div> : stats ? (
        <div className="grid grid-cols-5 gap-3 mb-8">
          {[
            ['Total', stats.total, 'text-text'],
            ['Pending', stats.pending, 'text-warning'],
            ['Processing', stats.processing, 'text-accent'],
            ['Done', stats.completed, 'text-success'],
            ['Failed', stats.failed, 'text-danger'],
          ].map(([label, value, color]) => (
            <div key={label as string} className="rounded-lg border border-border bg-card p-4 text-center">
              <p className={`text-2xl font-bold ${color} tabular-nums`}>{value as number}</p>
              <p className="text-[11px] font-medium text-text-tertiary mt-0.5">{label as string}</p>
            </div>
          ))}
        </div>
      ) : null}

      {/* Pending */}
      <section className="mb-6">
        <h2 className="text-[15px] font-semibold text-text mb-2">Pending Jobs</h2>
        {pendingLoading ? <Spinner /> : pending.length === 0 ? (
          <p className="text-[12px] text-text-tertiary">保留中のジョブはありません</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-border bg-sidebar/50">
                  <th className="px-3 py-2 text-left font-medium text-text-tertiary">File</th>
                  <th className="px-3 py-2 text-left font-medium text-text-tertiary">Op</th>
                  <th className="px-3 py-2 text-left font-medium text-text-tertiary">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {pending.map((job) => (
                  <tr key={job.queue_id} className="hover:bg-hover/50">
                    <td className="px-3 py-2 text-text truncate max-w-60">{job.file_path}</td>
                    <td className="px-3 py-2"><span className="rounded bg-warning-subtle px-1.5 py-0.5 text-[10px] font-medium text-warning">{job.operation}</span></td>
                    <td className="px-3 py-2 text-text-tertiary tabular-nums">{formatRelativeTime(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Failed */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-[15px] font-semibold text-text">Failed Jobs</h2>
          {failed.length > 0 && (
            <button onClick={() => { clearFailed.mutate(); addToast({ type: 'success', title: 'クリアしました' }) }}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-danger hover:bg-danger-subtle transition-colors cursor-pointer">
              <Trash2 size={12} />Clear all
            </button>
          )}
        </div>
        {failedLoading ? <Spinner /> : failed.length === 0 ? (
          <p className="text-[12px] text-text-tertiary">失敗ジョブはありません</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-border bg-sidebar/50">
                  <th className="px-3 py-2 text-left font-medium text-text-tertiary">File</th>
                  <th className="px-3 py-2 text-left font-medium text-text-tertiary">Error</th>
                  <th className="px-3 py-2 text-right font-medium text-text-tertiary">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {failed.map((job) => (
                  <tr key={job.queue_id} className="hover:bg-hover/50">
                    <td className="px-3 py-2 text-text truncate max-w-48">{job.file_path}</td>
                    <td className="px-3 py-2 text-danger truncate max-w-72 text-[11px]">{job.last_error || '—'}</td>
                    <td className="px-3 py-2 text-right">
                      <button onClick={() => { retryJob.mutate(job.queue_id); addToast({ type: 'info', title: '再試行開始' }) }}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-text-secondary hover:bg-hover transition-colors cursor-pointer">
                        <RotateCw size={12} />Retry
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
