import { HardDrive, FileText, Layers, Clock, AlertTriangle, Activity } from 'lucide-react'
import { Spinner } from '@/components/ui/Spinner'
import { useMetrics, useHealth } from '@/hooks/useSettings'

export default function SystemPage() {
  const { data: metricsData, isLoading } = useMetrics()
  const { data: healthData } = useHealth()

  const metrics = metricsData?.data
  const health = healthData
  const isHealthy = health?.status === 'ok'

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-bold text-text tracking-tight">System</h1>
          <p className="text-[13px] text-text-secondary mt-0.5">システムの状態とメトリクス</p>
        </div>
        {health && (
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${isHealthy ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${isHealthy ? 'bg-success' : 'bg-danger'}`} />
            {isHealthy ? 'Healthy' : 'Degraded'}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : metrics ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {([
            ['Documents', metrics.total_documents, FileText, false],
            ['Chunks', metrics.total_chunks, Layers, false],
            ['Queue Pending', metrics.indexing_queue_pending, Clock, false],
            ['Queue Failed', metrics.indexing_queue_failed, AlertTriangle, false],
            ['Total Queue', metrics.total_queue_items, Activity, false],
            ['Vault', metrics.vault_path, HardDrive, true],
          ] as const).map(([label, value, Icon, full]) => (
            <div key={label as string} className={`rounded-lg border border-border bg-card p-4 ${full ? 'col-span-2' : ''}`}>
              <Icon size={18} className="text-text-tertiary mb-2" />
              <p className={`${full ? 'text-[14px]' : 'text-2xl'} font-bold text-text tabular-nums ${full ? 'truncate' : ''}`}>
                {String(value)}
              </p>
              <p className="text-[11px] font-medium text-text-tertiary mt-0.5">{label as string}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-sm text-text-secondary">APIサーバーが応答していません</p>
        </div>
      )}
    </div>
  )
}
