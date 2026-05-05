import { motion } from 'framer-motion'
import { HardDrive, FileText, Layers, AlertTriangle, Clock, Activity } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { useMetrics, useHealth } from '@/hooks/useSettings'

export default function SystemPage() {
  const { data: metricsData, isLoading: metricsLoading } = useMetrics()
  const { data: healthData } = useHealth()

  const metrics = metricsData?.data
  const health = healthData
  const isHealthy = health?.status === 'ok'

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">システム情報</h1>
          <p className="text-sm text-text-muted mt-1">システムの状態とメトリクス</p>
        </div>
        {health && (
          <Badge variant={isHealthy ? 'success' : 'danger'} dot>
            {isHealthy ? '正常' : '異常'}
          </Badge>
        )}
      </div>

      {metricsLoading ? (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      ) : metrics ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card className="flex items-center gap-4">
            <FileText size={24} className="text-primary" />
            <div>
              <p className="text-2xl font-bold text-text-primary">{metrics.total_documents}</p>
              <p className="text-xs text-text-muted">総ドキュメント数</p>
            </div>
          </Card>

          <Card className="flex items-center gap-4">
            <Layers size={24} className="text-primary" />
            <div>
              <p className="text-2xl font-bold text-text-primary">{metrics.total_chunks}</p>
              <p className="text-xs text-text-muted">総チャンク数</p>
            </div>
          </Card>

          <Card className="flex items-center gap-4">
            <Clock size={24} className="text-warning" />
            <div>
              <p className="text-2xl font-bold text-text-primary">{metrics.indexing_queue_pending}</p>
              <p className="text-xs text-text-muted">保留中キュー</p>
            </div>
          </Card>

          <Card className="flex items-center gap-4">
            <AlertTriangle size={24} className="text-danger" />
            <div>
              <p className="text-2xl font-bold text-text-primary">{metrics.indexing_queue_failed}</p>
              <p className="text-xs text-text-muted">失敗キュー</p>
            </div>
          </Card>

          <Card className="flex items-center gap-4">
            <Activity size={24} className="text-primary" />
            <div>
              <p className="text-2xl font-bold text-text-primary">{metrics.total_queue_items}</p>
              <p className="text-xs text-text-muted">総キューアイテム</p>
            </div>
          </Card>

          <Card className="flex items-center gap-4">
            <HardDrive size={24} className="text-text-secondary" />
            <div>
              <p className="text-lg font-bold text-text-primary truncate max-w-48">
                {metrics.vault_path}
              </p>
              <p className="text-xs text-text-muted">Vault パス</p>
            </div>
          </Card>
        </div>
      ) : (
        <Card className="flex flex-col items-center py-12">
          <p className="text-text-muted">メトリクスを取得できません</p>
          <p className="text-sm text-text-muted mt-1">APIサーバーが起動しているか確認してください</p>
        </Card>
      )}

      {metrics && (
        <div className="mt-6 flex items-center gap-4 text-sm text-text-muted">
          <span>DBサイズ: {metrics.db_size_mb ? `${metrics.db_size_mb} MB` : 'N/A'}</span>
          <span>バージョン: v{metrics.version}</span>
        </div>
      )}
    </motion.div>
  )
}
