import { FolderOpen, ChevronRight, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { FolderItem } from '@/types/api'

interface FolderTreeProps {
  folders: FolderItem[]
  selected: string | null
  onSelect: (path: string | null) => void
}

interface TreeNode {
  name: string
  fullPath: string
  count: number
  children: TreeNode[]
}

function buildTree(folders: FolderItem[]): TreeNode[] {
  const root: TreeNode[] = []
  for (const f of folders) {
    const parts = f.folder_path.replace(/\/$/, '').split('/')
    let current = root
    let currentPath = ''
    for (const part of parts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part
      let node = current.find((n) => n.name === part)
      if (!node) {
        node = { name: part, fullPath: currentPath + '/', count: 0, children: [] }
        current.push(node)
      }
      node.count += f.note_count
      current = node.children
    }
  }
  return root
}

function TreeNodeItem({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: TreeNode
  depth: number
  selected: string | null
  onSelect: (path: string | null) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children.length > 0
  const isSelected = selected === node.fullPath

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) setExpanded(!expanded)
          onSelect(isSelected ? null : node.fullPath)
        }}
        className={cn(
          'w-full flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-colors group cursor-pointer',
          isSelected
            ? 'bg-primary-subtle text-primary font-medium'
            : 'text-text-secondary hover:bg-surface-hover',
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {hasChildren ? (
          expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
        ) : (
          <span className="w-3.5" />
        )}
        <FolderOpen size={14} className="shrink-0" />
        <span className="truncate flex-1 text-left">{node.name}</span>
        <span className="text-xs text-text-muted">{node.count}</span>
      </button>
      {hasChildren && (
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: 'auto' }}
              exit={{ height: 0 }}
              className="overflow-hidden"
            >
              {node.children.map((child) => (
                <TreeNodeItem
                  key={child.fullPath}
                  node={child}
                  depth={depth + 1}
                  selected={selected}
                  onSelect={onSelect}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  )
}

export function FolderTree({ folders, selected, onSelect }: FolderTreeProps) {
  const tree = buildTree(folders)

  return (
    <div className="space-y-0.5">
      <button
        onClick={() => onSelect(null)}
        className={cn(
          'w-full text-left px-3 py-1.5 text-sm rounded-md transition-colors cursor-pointer',
          selected === null
            ? 'bg-primary-subtle text-primary font-medium'
            : 'text-text-secondary hover:bg-surface-hover',
        )}
      >
        すべてのノート
      </button>
      {tree.map((node) => (
        <TreeNodeItem
          key={node.fullPath}
          node={node}
          depth={0}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
