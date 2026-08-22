import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info'

const toneClasses: Record<Tone, string> = {
  neutral: 'bg-border/60 text-text-muted',
  brand: 'bg-brand-500/15 text-brand-600 dark:text-brand-300',
  success: 'bg-success-500/15 text-success-600 dark:text-success-500',
  warning: 'bg-warning-500/15 text-warning-600 dark:text-warning-500',
  danger: 'bg-danger-500/15 text-danger-600 dark:text-danger-500',
  info: 'bg-info-500/15 text-info-500',
}

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
}

export function Badge({ className, tone = 'neutral', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium leading-none',
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  )
}
