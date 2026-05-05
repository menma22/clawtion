import { motion } from 'framer-motion'
import { RotateCw, Play, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
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
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">キュー管理</h1>
          <p className="text-sm text-text-muted mt-1">Indexing ジョブの状態と管理</p>
        </div>
        <Button onClick={() => processQueue.mutate()} loading={processQueue.isPending}>
          <Play size={16} />
          キュー処理
        </Button>
      </div>

      {/* Stats cards */}
      {statsLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          {[
            ['合計', stats.total, 'default'],
            ['保留中', stats.pending, 'warning'],
            ['処理中', stats.processing, 'info'],
            ['完了', stats.completed, 'success'],
            ['失敗', stats.failed, 'danger'],
          ].map(([label, value, variant]) => (
            <Card key={label as string} className="text-center py-4">
              <p className="text-2xl font-bold text-text-primary">{value as number}</p>
              <Badge variant={variant as 'success' | 'warning' | 'danger' | 'info' | 'default'}>
                {label as string}
              </Badge>
            </Card>
          ))}
        </div>
      ) : null}

      {/* Pending jobs */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-text-primary mb-3">保留中ジョブ</h2>
        {pendingLoading ? (
          <Spinner />
        ) : pending.length === 0 ? (
          <p className="text-sm text-text-muted">保留中のジョブはありません</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border-default">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-default bg-surface-sidebar">
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">ファイル</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">操作</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">優先度</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">作成日</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {pending.map((job) => (
                  <tr key={job.queue_id} className="hover:bg-surface-hover">
                    <td className="px-3 py-2 text-text-primary truncate max-w-40">{job.file_path}</td>
                    <td className="px-3 py-2"><Badge variant="warning">{job.operation}</Badge></td>
                    <td className="px-3 py-2 text-text-muted">{job.priority}</td>
                    <td className="px-3 py-2 text-text-muted">{formatRelativeTime(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Failed jobs */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-text-primary">失敗ジョブ</h2>
          {failed.length > 0 && (
            <Button variant="danger" size="sm" onClick={() => {
              clearFailed.mutate()
              addToast({ type: 'success', title: '失敗ジョブをクリアしました' })
            }}>
              <Trash2 size={14} />
              すべてクリア
            </Button>
          )}
        </div>
        {failedLoading ? (
          <Spinner />
        ) : failed.length === 0 ? (
          <p className="text-sm text-text-muted">失敗したジョブはありません</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border-default">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-default bg-surface-sidebar">
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">ファイル</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">エラー</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-text-muted">リトライ</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-text-muted">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {failed.map((job) => (
                  <tr key={job.queue_id} className="hover:bg-surface-hover">
                    <td className="px-3 py-2 text-text-primary truncate max-w-40">{job.file_path}</td>
                    <td className="px-3 py-2 text-danger text-xs truncate max-w-60">{job.last_error || '-'}</td>
                    <td className="px-3 py-2 text-text-muted">{job.retry_count}/{job.max_retries}</td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          retryJob.mutate(job.queue_id)
                          addToast({ type: 'info', title: '再試行を開始しました' })
                        }}
                      >
                        <RotateCw size={14} />
                        再試行
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </motion.div>
  )
}
