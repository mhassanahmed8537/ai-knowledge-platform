import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { createContext, use, useCallback, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

type ToastTone = 'success' | 'error' | 'info'

interface Toast {
  id: string
  tone: ToastTone
  title: string
  description?: string
}

interface ToastContextValue {
  push: (toast: Omit<Toast, 'id'>) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const toneConfig: Record<ToastTone, { icon: typeof CheckCircle2; classes: string }> = {
  success: { icon: CheckCircle2, classes: 'text-success-500' },
  error: { icon: AlertCircle, classes: 'text-danger-500' },
  info: { icon: Info, classes: 'text-info-500' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = crypto.randomUUID()
      setToasts((current) => [...current, { ...toast, id }])
      setTimeout(() => dismiss(id), 5000)
    },
    [dismiss],
  )

  return (
    <ToastContext value={{ push }}>
      {children}
      {createPortal(
        <div className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
          <AnimatePresence>
            {toasts.map((toast) => {
              const { icon: Icon, classes } = toneConfig[toast.tone]
              return (
                <motion.div
                  key={toast.id}
                  layout
                  initial={{ opacity: 0, y: 12, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, x: 40, transition: { duration: 0.15 } }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className="flex items-start gap-3 rounded-xl border border-border bg-surface-raised p-4 shadow-[var(--shadow-soft)] dark:shadow-[var(--shadow-soft-dark)]"
                >
                  <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', classes)} />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-text">{toast.title}</p>
                    {toast.description && (
                      <p className="mt-0.5 text-sm text-text-muted">{toast.description}</p>
                    )}
                  </div>
                  <button
                    onClick={() => dismiss(toast.id)}
                    className="text-text-faint hover:text-text"
                    aria-label="Dismiss"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>,
        document.body,
      )}
    </ToastContext>
  )
}

export function useToast(): ToastContextValue {
  const ctx = use(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
