import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: ReactNode
  icon: LucideIcon
  tone?: 'default' | 'danger' | 'success'
  sub?: ReactNode
}

export function StatCard({ label, value, icon: Icon, tone = 'default', sub }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-2xl border border-border bg-surface p-5 shadow-[var(--shadow-soft)] dark:shadow-[var(--shadow-soft-dark)]"
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text-muted">{label}</p>
        <div
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-lg',
            tone === 'danger' && 'bg-danger-500/10 text-danger-500',
            tone === 'success' && 'bg-success-500/10 text-success-600',
            tone === 'default' && 'bg-brand-500/10 text-brand-500',
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight text-text">{value}</div>
      {sub && <div className="mt-1 text-sm text-text-faint">{sub}</div>}
    </motion.div>
  )
}
