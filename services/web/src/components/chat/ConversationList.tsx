import { motion } from 'framer-motion'
import { MessageSquare, Plus } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import type { ConversationOut } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { cn, formatRelativeTime } from '@/lib/utils'

interface ConversationListProps {
  conversations: ConversationOut[]
  isLoading: boolean
  onNew: () => void
  className?: string
}

export function ConversationList({ conversations, isLoading, onNew, className }: ConversationListProps) {
  return (
    <div className={cn('flex h-full flex-col border-r border-border', className)}>
      <div className="p-4">
        <Button onClick={onNew} className="w-full justify-center" size="sm">
          <Plus className="h-4 w-4" />
          New chat
        </Button>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-4">
        {isLoading && (
          <div className="space-y-2 px-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-border/40" />
            ))}
          </div>
        )}
        {!isLoading && conversations.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-text-faint">No conversations yet</p>
        )}
        {conversations.map((conv, i) => (
          <motion.div
            key={conv.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, delay: Math.min(i, 6) * 0.02 }}
          >
            <NavLink
              to={`/chat/${conv.id}`}
              className={({ isActive }) =>
                cn(
                  'flex items-start gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-colors',
                  isActive ? 'bg-brand-500/12 text-brand-600 dark:text-brand-300' : 'text-text-muted hover:bg-border/40 hover:text-text',
                )
              }
            >
              <MessageSquare className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{conv.title || 'New conversation'}</p>
                <p className="truncate text-xs text-text-faint">{formatRelativeTime(conv.created_at)}</p>
              </div>
            </NavLink>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
