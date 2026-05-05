import { motion } from 'framer-motion'
import { AlertCircle } from 'lucide-react'
import { Card } from '@/components/ui/Card'

export default function TrashPage() {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="p-6">
      <h1 className="text-2xl font-bold text-text-primary mb-6">ゴミ箱</h1>

      <Card className="flex flex-col items-center text-center py-12 gap-3">
        <AlertCircle size={40} className="text-warning" />
        <div>
          <p className="text-text-primary font-medium mb-1">API エンドポイント準備中</p>
          <p className="text-sm text-text-muted max-w-md">
            ゴミ箱の一覧表示・復元機能は現在バックエンドAPIの対応待ちです。
            CLIコマンド <code className="text-xs bg-surface-input px-1 py-0.5 rounded">clawtion trash list</code> で
            ゴミ箱の内容を確認できます。
          </p>
        </div>
      </Card>
    </motion.div>
  )
}
