import { FolderOpen, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { FolderItem } from '@/types/api'

interface FolderTreeProps {
  folders: FolderItem[]; selected: string | null; onSelect: (path: string | null) => void
}

interface TreeNode {
  name: string; fullPath: string; count: number; children: TreeNode[]
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
      if (!node) { node = { name: part, fullPath: currentPath + '/', count: 0, children: [] }; current.push(node) }
      node.count += f.note_count
      current = node.children
    }
  }
  return root
}

function TreeNodeItem({ node, depth, selected, onSelect }: {
  node: TreeNode; depth: number; selected: string | null; onSelect: (path: string | null) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children.length > 0
  const isSelected = selected === node.fullPath

  return (
    <div>
      <button
        onClick={() => { if (hasChildren) setExpanded(!expanded); onSelect(isSelected ? null : node.fullPath) }}
        className={cn(
          'w-full flex items-center gap-1 rounded-md px-2 py-1 text-[12px] transition-colors cursor-pointer',
          isSelected ? 'bg-accent-subtle text-accent font-medium' : 'text-text-secondary hover:bg-hover',
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        {hasChildren ? (
          <motion.span animate={{ rotate: expanded ? 90 : 0 }} transition={{ duration: 0.15 }}>
            <ChevronRight size={12} />
          </motion.span>
        ) : <span className="w-3" />}
        <FolderOpen size={12} className="shrink-0" />
        <span className="truncate flex-1 text-left">{node.name}</span>
        <span className="text-[10px] text-text-tertiary">{node.count}</span>
      </button>
      {hasChildren && (
        <AnimatePresence>
          {expanded && (
            <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
              {node.children.map((child) => (
                <TreeNodeItem key={child.fullPath} node={child} depth={depth + 1} selected={selected} onSelect={onSelect} />
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
    <div className="space-y-0">
      {tree.map((node) => (
        <TreeNodeItem key={node.fullPath} node={node} depth={0} selected={selected} onSelect={onSelect} />
      ))}
    </div>
  )
}
