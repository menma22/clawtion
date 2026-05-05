import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useUIStore, type Toast as ToastType } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

const iconMap = { success: CheckCircle, error: XCircle, warning: AlertTriangle, info: Info }
const accentMap = {
  success: 'border-accent/30 bg-card',
  error: 'border-danger/30 bg-card',
  warning: 'border-warning/30 bg-card',
  info: 'border-accent/30 bg-card',
}

function ToastItem({ toast }: { toast: ToastType }) {
  const removeToast = useUIStore((s) => s.removeToast)
  const Icon = iconMap[toast.type]

  useEffect(() => {
    const timer = setTimeout(() => removeToast(toast.id), 5000)
    return () => clearTimeout(timer)
  }, [toast.id, removeToast])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className={cn(
        'flex w-80 items-start gap-2.5 rounded-lg border p-3 shadow-lg',
        accentMap[toast.type],
      )}
    >
      <Icon size={15} className="mt-0.5 shrink-0 text-text-secondary" />
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-text">{toast.title}</p>
        {toast.message && <p className="text-[11px] text-text-secondary mt-0.5">{toast.message}</p>}
      </div>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 rounded p-0.5 text-text-tertiary hover:text-text-secondary transition-colors cursor-pointer"
      >
        <X size={13} />
      </button>
    </motion.div>
  )
}

export function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts)
  return (
    <div className="pointer-events-none fixed bottom-3 right-3 z-40 flex flex-col gap-2">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  )
}
