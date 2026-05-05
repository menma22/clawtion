import { AlertCircle } from 'lucide-react'

export default function TrashPage() {
  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="text-[22px] font-bold text-text tracking-tight mb-6">Trash</h1>
      <div className="flex flex-col items-center justify-center py-20 text-center rounded-lg border border-border bg-card">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-hover mb-4">
          <AlertCircle size={22} className="text-text-tertiary" />
        </div>
        <h3 className="text-[15px] font-semibold text-text mb-1">API準備中</h3>
        <p className="text-[13px] text-text-secondary max-w-sm">
          ゴミ箱機能はバックエンドAPI対応待ちです。<br />
          CLI: <code className="text-[12px] bg-input px-1 py-0.5 rounded text-accent">clawtion trash list</code>
        </p>
      </div>
    </div>
  )
}
