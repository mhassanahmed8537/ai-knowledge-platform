import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border-strong px-6 py-16 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-500/10 text-brand-500">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-[15px] font-semibold text-text">{title}</h3>
      {description && <p className="max-w-sm text-sm text-text-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </motion.div>
  )
}
