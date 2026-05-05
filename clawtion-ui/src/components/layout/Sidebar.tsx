import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  FileText,
  Search,
  BarChart3,
  Trash2,
  Monitor,
  Settings,
  ChevronLeft,
  Database,
  FolderOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores/uiStore'
import { useFolders } from '@/hooks/useSettings'
import { useNoteStore } from '@/stores/noteStore'
import { useQueueStatus } from '@/hooks/useQueue'

const navItems = [
  { to: '/notes', icon: FileText, label: 'ノート' },
  { to: '/search', icon: Search, label: '検索' },
  { to: '/queue', icon: BarChart3, label: 'キュー', hasBadge: true },
  { to: '/trash', icon: Trash2, label: 'ゴミ箱' },
  { to: '/system', icon: Monitor, label: 'システム' },
  { to: '/settings', icon: Settings, label: '設定' },
]

export function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const toggle = useUIStore((s) => s.toggleSidebar)
  const location = useLocation()
  const { data: foldersData } = useFolders()
  const folderFilter = useNoteStore((s) => s.folderFilter)
  const setFolderFilter = useNoteStore((s) => s.setFolderFilter)
  const { data: queueData } = useQueueStatus()
  const pendingCount = queueData?.data?.pending ?? 0

  const folders = foldersData?.data ?? []

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 0 : 260 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="h-full overflow-hidden border-r border-border-default bg-surface-sidebar flex flex-col shrink-0"
    >
      <div className="flex h-12 items-center justify-between px-4 border-b border-border-default">
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2"
          >
            <Database size={20} className="text-primary" />
            <span className="font-semibold text-sm text-text-primary">clawtion</span>
          </motion.div>
        )}
        <button
          onClick={toggle}
          className="rounded-md p-1 text-text-muted hover:bg-surface-input hover:text-text-secondary transition-colors cursor-pointer shrink-0"
          aria-label={collapsed ? 'サイドバーを開く' : 'サイドバーを閉じる'}
        >
          <motion.div
            animate={{ rotate: collapsed ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronLeft size={16} />
          </motion.div>
        </button>
      </div>

      {!collapsed && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="flex-1 overflow-y-auto"
        >
          <nav className="p-2 space-y-1">
            {navItems.map(({ to, icon: Icon, label, hasBadge }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive || (to === '/notes' && location.pathname.startsWith('/notes'))
                      ? 'bg-primary-subtle text-primary'
                      : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                  )
                }
              >
                <Icon size={18} />
                <span className="flex-1">{label}</span>
                {hasBadge && pendingCount > 0 && (
                  <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-text-inverse">
                    {pendingCount}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Folder tree */}
          {folders.length > 0 && (
            <div className="px-2 mt-4">
              <div className="flex items-center gap-2 px-3 py-1 text-xs font-medium text-text-muted uppercase tracking-wider">
                <FolderOpen size={12} />
                フォルダ
              </div>
              <div className="mt-1 space-y-0.5">
                <button
                  onClick={() => setFolderFilter(null)}
                  className={cn(
                    'w-full text-left px-3 py-1.5 text-sm rounded-md transition-colors cursor-pointer',
                    folderFilter === null
                      ? 'bg-primary-subtle text-primary font-medium'
                      : 'text-text-secondary hover:bg-surface-hover',
                  )}
                >
                  すべて
                </button>
                {folders.map((f) => (
                  <button
                    key={f.folder_path}
                    onClick={() =>
                      setFolderFilter(
                        folderFilter === f.folder_path ? null : f.folder_path,
                      )
                    }
                    className={cn(
                      'w-full text-left px-3 py-1.5 text-sm rounded-md transition-colors flex items-center justify-between cursor-pointer',
                      folderFilter === f.folder_path
                        ? 'bg-primary-subtle text-primary font-medium'
                        : 'text-text-secondary hover:bg-surface-hover',
                    )}
                  >
                    <span className="truncate">{f.folder_path.replace(/\/$/, '')}</span>
                    <span className="text-xs text-text-muted ml-2 shrink-0">{f.note_count}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </motion.aside>
  )
}
