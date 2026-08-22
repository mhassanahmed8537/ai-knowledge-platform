import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Copy, Plus, Trash2, Webhook as WebhookIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError } from '@/api/client'
import { webhooksApi } from '@/api/webhooks'
import type { WebhookCreated, WebhookEvent, WebhookOut } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { PageSpinner } from '@/components/ui/Spinner'
import { useToast } from '@/context/ToastContext'
import { cn, formatDateTime } from '@/lib/utils'

const EVENT_OPTIONS: { value: WebhookEvent; label: string; hint: string }[] = [
  { value: 'document.ready', label: 'document.ready', hint: 'A document finished processing' },
  { value: 'document.failed', label: 'document.failed', hint: 'A document failed to process' },
  { value: 'budget.alert', label: 'budget.alert', hint: 'Monthly spend crossed the budget' },
]

export function Webhooks() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [createOpen, setCreateOpen] = useState(false)
  const [revealed, setRevealed] = useState<WebhookCreated | null>(null)
  const [deleting, setDeleting] = useState<WebhookOut | null>(null)

  const webhooksQuery = useQuery({ queryKey: ['webhooks'], queryFn: webhooksApi.list })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => webhooksApi.delete(id),
    onSuccess: (_void, id) => {
      queryClient.setQueryData<WebhookOut[]>(['webhooks'], (old = []) => old.filter((w) => w.id !== id))
    },
  })

  const webhooks = webhooksQuery.data ?? []

  return (
    <div>
      <PageHeader
        title="Webhooks"
        description="Get notified when documents finish processing or spend crosses budget."
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Add webhook
          </Button>
        }
      />

      <div className="px-6 pb-10 sm:px-8">
        {webhooksQuery.isLoading && <PageSpinner />}

        {!webhooksQuery.isLoading && webhooks.length === 0 && (
          <EmptyState
            icon={WebhookIcon}
            title="No webhooks yet"
            description="Add an endpoint to receive event notifications as they happen."
          />
        )}

        <div className="space-y-2">
          <AnimatePresence initial={false}>
            {webhooks.map((hook) => (
              <motion.div
                key={hook.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-center gap-4 rounded-xl border border-border bg-surface p-4"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-500/10 text-brand-500">
                  <WebhookIcon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text">{hook.url}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {hook.event_types.map((et) => (
                      <Badge key={et} tone="brand">
                        {et}
                      </Badge>
                    ))}
                    {!hook.is_active && <Badge tone="neutral">disabled</Badge>}
                  </div>
                  <p className="mt-1.5 text-xs text-text-faint">Added {formatDateTime(hook.created_at)}</p>
                </div>
                <button
                  onClick={() => setDeleting(hook)}
                  className="shrink-0 rounded-lg p-2 text-text-faint transition-colors hover:bg-danger-500/10 hover:text-danger-500"
                  aria-label="Delete webhook"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      <CreateWebhookModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => {
          queryClient.setQueryData<WebhookOut[]>(['webhooks'], (old = []) => [created, ...old])
          setCreateOpen(false)
          setRevealed(created)
        }}
      />

      <Modal
        open={!!revealed}
        onClose={() => setRevealed(null)}
        title="Webhook created"
        description="Copy the signing secret now — it won't be shown again."
      >
        {revealed && <SecretReveal value={revealed.secret} />}
        <div className="mt-4 flex justify-end">
          <Button onClick={() => setRevealed(null)}>Done</Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete webhook?"
        description={deleting ? `${deleting.url} will stop receiving events immediately.` : undefined}
        confirmLabel="Delete"
        onConfirm={async () => {
          if (deleting) {
            await deleteMutation.mutateAsync(deleting.id)
            toast.push({ tone: 'success', title: 'Webhook deleted' })
          }
        }}
      />
    </div>
  )
}

function CreateWebhookModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (created: WebhookCreated) => void
}) {
  const [url, setUrl] = useState('')
  const [eventTypes, setEventTypes] = useState<WebhookEvent[]>(['document.ready'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setUrl('')
    setEventTypes(['document.ready'])
    setError(null)
  }

  const toggleEvent = (value: WebhookEvent) => {
    setEventTypes((current) =>
      current.includes(value) ? current.filter((e) => e !== value) : [...current, value],
    )
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (eventTypes.length === 0) {
      setError('Select at least one event type')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const created = await webhooksApi.create({ url: url.trim(), event_types: eventTypes })
      reset()
      onCreated(created)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create webhook')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        reset()
        onClose()
      }}
      title="Add webhook"
      description="We'll POST a signed JSON payload to this URL for the events you select."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Endpoint URL"
          type="url"
          placeholder="https://example.com/hooks/knowledge-platform"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-text">Events</span>
          <div className="flex flex-col gap-2">
            {EVENT_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-lg border border-border-strong px-3.5 py-2.5 transition-colors',
                  eventTypes.includes(opt.value) && 'border-brand-500 bg-brand-500/5',
                )}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded border-border-strong text-brand-600 focus:ring-ring"
                  checked={eventTypes.includes(opt.value)}
                  onChange={() => toggleEvent(opt.value)}
                />
                <span>
                  <span className="block text-sm font-medium text-text">{opt.label}</span>
                  <span className="block text-xs text-text-faint">{opt.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
        {error && <p className="text-sm text-danger-500">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Create
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function SecretReveal({ value }: { value: string }) {
  const toast = useToast()
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.push({ tone: 'error', title: 'Could not copy', description: 'Copy the value manually instead.' })
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border-strong bg-bg px-3.5 py-2.5">
      <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-sm text-text">{value}</code>
      <button
        onClick={handleCopy}
        className="shrink-0 rounded-md p-1.5 text-text-faint transition-colors hover:bg-border/50 hover:text-text"
        aria-label="Copy to clipboard"
      >
        {copied ? <Check className="h-4 w-4 text-success-500" /> : <Copy className="h-4 w-4" />}
      </button>
    </div>
  )
}
