import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('h-5 w-5 animate-spin text-text-faint', className)} />
}

export function PageSpinner() {
  return (
    <div className="flex h-full min-h-64 w-full items-center justify-center">
      <Spinner className="h-7 w-7" />
    </div>
  )
}
