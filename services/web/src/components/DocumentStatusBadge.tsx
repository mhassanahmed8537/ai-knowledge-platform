import { CheckCircle2, CircleDashed, Loader2, XCircle } from 'lucide-react'
import type { DocumentStatus } from '@/api/types'
import { Badge } from '@/components/ui/Badge'

const CONFIG: Record<DocumentStatus, { tone: 'neutral' | 'brand' | 'success' | 'danger'; icon: typeof CheckCircle2; label: string }> = {
  pending: { tone: 'neutral', icon: CircleDashed, label: 'Pending' },
  processing: { tone: 'brand', icon: Loader2, label: 'Processing' },
  ready: { tone: 'success', icon: CheckCircle2, label: 'Ready' },
  failed: { tone: 'danger', icon: XCircle, label: 'Failed' },
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const { tone, icon: Icon, label } = CONFIG[status]
  return (
    <Badge tone={tone}>
      <Icon className={`h-3 w-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {label}
    </Badge>
  )
}
