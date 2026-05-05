import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  FileText, Search, BarChart3, Trash2, Monitor,
  Settings, ChevronLeft, Database, Plus, FolderOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores/uiStore'
import { useFolders } from '@/hooks/useSettings'
import { useNoteStore } from '@/stores/noteStore'
import { useQueueStatus } from '@/hooks/useQueue'
import { useNavigate } from 'react-router-dom'

const navItems = [
  { to: '/notes', icon: FileText, label: 'Notes' },
  { to: '/search', icon: Search, label: 'Search' },
  { to: '/queue', icon: BarChart3, label: 'Queue', hasBadge: true },
  { to: '/trash', icon: Trash2, label: 'Trash' },
  { to: '/system', icon: Monitor, label: 'System' },
]

export function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const toggle = useUIStore((s) => s.toggleSidebar)
  const location = useLocation()
  const navigate = useNavigate()
  const { data: foldersData } = useFolders()
  const folderFilter = useNoteStore((s) => s.folderFilter)
  const setFolderFilter = useNoteStore((s) => s.setFolderFilter)
  const { data: queueData } = useQueueStatus()
  const pendingCount = queueData?.data?.pending ?? 0

  const folders = foldersData?.data ?? []

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 0 : 240 }}
      transition={{ type: 'spring', stiffness: 400, damping: 35 }}
      className="flex h-full shrink-0 flex-col overflow-hidden border-r border-border bg-sidebar"
    >
      {/* Header */}
      <div className="flex h-11 items-center justify-between px-3">
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2"
          >
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-text">
              <Database size={14} className="text-app" />
            </div>
            <span className="text-[13px] font-semibold text-text tracking-tight">clawtion</span>
          </motion.div>
        )}
        <button
          onClick={toggle}
          className={cn(
            'rounded-md p-1 text-text-tertiary hover:bg-hover hover:text-text-secondary transition-colors cursor-pointer',
            collapsed && 'mx-auto',
          )}
        >
          <motion.div animate={{ rotate: collapsed ? 0 : 0 }}>
            <ChevronLeft size={15} className={cn(collapsed && 'rotate-180')} />
          </motion.div>
        </button>
      </div>

      {!collapsed && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-1 flex-col overflow-hidden">
          {/* New Note button */}
          <div className="px-2 pb-1">
            <button
              onClick={() => navigate('/notes/new')}
              className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] font-medium text-text-secondary hover:bg-hover transition-colors cursor-pointer"
            >
              <Plus size={15} />
              新規ノート
            </button>
          </div>

          {/* Nav items */}
          <nav className="px-2 space-y-0.5">
            {navItems.map(({ to, icon: Icon, label, hasBadge }) => {
              const isActive = to === '/notes'
                ? location.pathname === '/' || location.pathname.startsWith('/notes')
                : location.pathname.startsWith(to)
              return (
                <NavLink
                  key={to}
                  to={to}
                  className={cn(
                    'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors',
                    isActive
                      ? 'bg-accent-subtle text-accent'
                      : 'text-text-secondary hover:bg-hover',
                  )}
                >
                  <Icon size={16} />
                  <span className="flex-1">{label}</span>
                  {hasBadge && pendingCount > 0 && (
                    <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-text-inverse">
                      {pendingCount}
                    </span>
                  )}
                </NavLink>
              )
            })}
          </nav>

          {/* Divider */}
          <div className="mx-2 my-1.5 border-t border-border" />

          {/* Settings */}
          <div className="px-2 pb-2">
            <NavLink
              to="/settings"
              className={cn(
                'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors',
                location.pathname.startsWith('/settings')
                  ? 'bg-accent-subtle text-accent'
                  : 'text-text-secondary hover:bg-hover',
              )}
            >
              <Settings size={16} />
              設定
            </NavLink>
          </div>

          {/* Folders */}
          <div className="flex-1 overflow-y-auto">
            {folders.length > 0 && (
              <div className="px-3 pt-1">
                <div className="flex items-center gap-1.5 px-1.5 py-0.5 text-[11px] font-medium text-text-tertiary uppercase tracking-wider">
                  <FolderOpen size={11} />
                  フォルダ
                </div>
                <div className="mt-0.5 space-y-0">
                  <button
                    onClick={() => setFolderFilter(null)}
                    className={cn(
                      'w-full text-left rounded-md px-2.5 py-1 text-[13px] transition-colors cursor-pointer',
                      folderFilter === null
                        ? 'text-accent font-medium'
                        : 'text-text-secondary hover:bg-hover',
                    )}
                  >
                    すべてのノート
                  </button>
                  {folders.map((f) => (
                    <button
                      key={f.folder_path}
                      onClick={() => setFolderFilter(folderFilter === f.folder_path ? null : f.folder_path)}
                      className={cn(
                        'w-full text-left rounded-md px-2.5 py-1 text-[13px] transition-colors flex items-center justify-between cursor-pointer',
                        folderFilter === f.folder_path
                          ? 'text-accent font-medium'
                          : 'text-text-secondary hover:bg-hover',
                      )}
                    >
                      <span className="truncate">{f.folder_path.replace(/\/$/, '')}</span>
                      <span className="text-[11px] text-text-tertiary ml-2 shrink-0">{f.note_count}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.aside>
  )
}
