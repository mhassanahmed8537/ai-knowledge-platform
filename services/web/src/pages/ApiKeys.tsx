import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { KeyRound, Plus, ShieldOff } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError } from '@/api/client'
import { apiKeysApi } from '@/api/apiKeys'
import type { ApiKeyCreated, ApiKeyOut } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { SecretReveal } from '@/pages/Webhooks'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { PageSpinner } from '@/components/ui/Spinner'
import { useToast } from '@/context/ToastContext'
import { formatDateTime } from '@/lib/utils'

export function ApiKeys() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [createOpen, setCreateOpen] = useState(false)
  const [revealed, setRevealed] = useState<ApiKeyCreated | null>(null)
  const [revoking, setRevoking] = useState<ApiKeyOut | null>(null)

  const keysQuery = useQuery({ queryKey: ['api-keys'], queryFn: apiKeysApi.list })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiKeysApi.revoke(id),
    onSuccess: (_void, id) => {
      queryClient.setQueryData<ApiKeyOut[]>(['api-keys'], (old = []) =>
        old.map((k) => (k.id === id ? { ...k, revoked_at: new Date().toISOString() } : k)),
      )
    },
  })

  const keys = keysQuery.data ?? []

  return (
    <div>
      <PageHeader
        title="API keys"
        description="Use API keys to call the platform programmatically, outside the browser."
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Create key
          </Button>
        }
      />

      <div className="px-6 pb-10 sm:px-8">
        {keysQuery.isLoading && <PageSpinner />}

        {!keysQuery.isLoading && keys.length === 0 && (
          <EmptyState icon={KeyRound} title="No API keys yet" description="Create a key to authenticate API requests." />
        )}

        <div className="overflow-hidden rounded-2xl border border-border bg-surface">
          {keys.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-faint">
                    <th className="px-5 py-2.5 font-medium">Name</th>
                    <th className="px-5 py-2.5 font-medium">Key</th>
                    <th className="px-5 py-2.5 font-medium">Last used</th>
                    <th className="px-5 py-2.5 font-medium">Expires</th>
                    <th className="px-5 py-2.5 font-medium">Status</th>
                    <th className="px-5 py-2.5 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence initial={false}>
                    {keys.map((key) => {
                      const revoked = !!key.revoked_at
                      const expired = !!key.expires_at && new Date(key.expires_at) < new Date()
                      return (
                        <motion.tr
                          key={key.id}
                          layout
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="border-b border-border/60 last:border-0"
                        >
                          <td className="px-5 py-3 font-medium text-text">{key.name}</td>
                          <td className="px-5 py-3 font-mono text-xs text-text-muted">{key.prefix}••••••••</td>
                          <td className="px-5 py-3 text-text-muted">
                            {key.last_used_at ? formatDateTime(key.last_used_at) : 'Never'}
                          </td>
                          <td className="px-5 py-3 text-text-muted">
                            {key.expires_at ? formatDateTime(key.expires_at) : 'No expiry'}
                          </td>
                          <td className="px-5 py-3">
                            {revoked ? (
                              <Badge tone="danger">revoked</Badge>
                            ) : expired ? (
                              <Badge tone="warning">expired</Badge>
                            ) : (
                              <Badge tone="success">active</Badge>
                            )}
                          </td>
                          <td className="px-5 py-3 text-right">
                            {!revoked && (
                              <button
                                onClick={() => setRevoking(key)}
                                className="rounded-lg p-2 text-text-faint transition-colors hover:bg-danger-500/10 hover:text-danger-500"
                                aria-label="Revoke key"
                              >
                                <ShieldOff className="h-4 w-4" />
                              </button>
                            )}
                          </td>
                        </motion.tr>
                      )
                    })}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <CreateApiKeyModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => {
          queryClient.setQueryData<ApiKeyOut[]>(['api-keys'], (old = []) => [created, ...old])
          setCreateOpen(false)
          setRevealed(created)
        }}
      />

      <Modal
        open={!!revealed}
        onClose={() => setRevealed(null)}
        title="API key created"
        description="Copy this key now — it won't be shown again."
      >
        {revealed && <SecretReveal value={revealed.key} />}
        <div className="mt-4 flex justify-end">
          <Button onClick={() => setRevealed(null)}>Done</Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!revoking}
        onClose={() => setRevoking(null)}
        title="Revoke API key?"
        description={revoking ? `"${revoking.name}" will stop working immediately. This can't be undone.` : undefined}
        confirmLabel="Revoke"
        onConfirm={async () => {
          if (revoking) {
            await revokeMutation.mutateAsync(revoking.id)
            toast.push({ tone: 'success', title: 'API key revoked' })
          }
        }}
      />
    </div>
  )
}

function CreateApiKeyModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (created: ApiKeyCreated) => void
}) {
  const [name, setName] = useState('')
  const [expiresInDays, setExpiresInDays] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setName('')
    setExpiresInDays('')
    setError(null)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const created = await apiKeysApi.create({
        name: name.trim(),
        expires_in_days: expiresInDays.trim() === '' ? null : Number(expiresInDays),
      })
      reset()
      onCreated(created)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create API key')
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
      title="Create API key"
      description="Keys inherit your account's role and permissions."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Name"
          placeholder="e.g. CI pipeline"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Input
          label="Expires in (days)"
          type="number"
          min="1"
          placeholder="Never expires"
          value={expiresInDays}
          onChange={(e) => setExpiresInDays(e.target.value)}
        />
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
