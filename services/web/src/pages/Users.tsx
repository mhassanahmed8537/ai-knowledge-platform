import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Plus, Trash2, Users as UsersIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError } from '@/api/client'
import { usersApi } from '@/api/users'
import type { UserCreate, UserOut, UserRole } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { PageSpinner } from '@/components/ui/Spinner'
import { useAuth } from '@/context/AuthContext'
import { useToast } from '@/context/ToastContext'
import { cn, formatDate, initials } from '@/lib/utils'

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'admin', label: 'Admin' },
  { value: 'member', label: 'Member' },
  { value: 'read_only', label: 'Read only' },
]

export function Users() {
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleting, setDeleting] = useState<UserOut | null>(null)

  const usersQuery = useQuery({ queryKey: ['users'], queryFn: usersApi.list })

  const updateMutation = useMutation({
    mutationFn: ({ id, role, is_active }: { id: string; role?: UserRole; is_active?: boolean }) =>
      usersApi.update(id, { role, is_active }),
    onSuccess: (updated) => {
      queryClient.setQueryData<UserOut[]>(['users'], (old = []) => old.map((u) => (u.id === updated.id ? updated : u)))
    },
    onError: (err) => {
      toast.push({
        tone: 'error',
        title: 'Update failed',
        description: err instanceof ApiError ? err.message : undefined,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => usersApi.delete(id),
    onSuccess: (_void, id) => {
      queryClient.setQueryData<UserOut[]>(['users'], (old = []) => old.filter((u) => u.id !== id))
    },
  })

  const users = usersQuery.data ?? []

  return (
    <div>
      <PageHeader
        title="Team"
        description="Manage who has access to this organization and their permissions."
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Invite user
          </Button>
        }
      />

      <div className="px-6 pb-10 sm:px-8">
        {usersQuery.isLoading && <PageSpinner />}

        {!usersQuery.isLoading && users.length === 0 && (
          <EmptyState icon={UsersIcon} title="No teammates yet" description="Invite someone to join this organization." />
        )}

        {users.length > 0 && (
          <div className="overflow-hidden rounded-2xl border border-border bg-surface">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-faint">
                    <th className="px-5 py-2.5 font-medium">User</th>
                    <th className="px-5 py-2.5 font-medium">Role</th>
                    <th className="px-5 py-2.5 font-medium">Status</th>
                    <th className="px-5 py-2.5 font-medium">Joined</th>
                    <th className="px-5 py-2.5 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence initial={false}>
                    {users.map((u) => {
                      const isSelf = u.id === me?.id
                      return (
                        <motion.tr
                          key={u.id}
                          layout
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="border-b border-border/60 last:border-0"
                        >
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-3">
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-xs font-semibold text-brand-600 dark:text-brand-300">
                                {initials(u.full_name ?? u.email)}
                              </div>
                              <div className="min-w-0">
                                <p className="truncate font-medium text-text">{u.full_name ?? u.email}</p>
                                <p className="truncate text-xs text-text-faint">{u.email}</p>
                              </div>
                              {isSelf && <Badge tone="neutral">You</Badge>}
                            </div>
                          </td>
                          <td className="px-5 py-3">
                            <select
                              value={u.role}
                              disabled={isSelf || updateMutation.isPending}
                              onChange={(e) => updateMutation.mutate({ id: u.id, role: e.target.value as UserRole })}
                              className={cn(
                                'rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-ring',
                                isSelf && 'cursor-not-allowed opacity-60',
                              )}
                            >
                              {ROLE_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-5 py-3">
                            <button
                              disabled={isSelf || updateMutation.isPending}
                              onClick={() => updateMutation.mutate({ id: u.id, is_active: !u.is_active })}
                              className={cn(!isSelf && 'cursor-pointer', isSelf && 'cursor-not-allowed')}
                            >
                              <Badge tone={u.is_active ? 'success' : 'neutral'}>
                                {u.is_active ? 'Active' : 'Deactivated'}
                              </Badge>
                            </button>
                          </td>
                          <td className="px-5 py-3 text-text-muted">{formatDate(u.created_at)}</td>
                          <td className="px-5 py-3 text-right">
                            {!isSelf && (
                              <button
                                onClick={() => setDeleting(u)}
                                className="rounded-lg p-2 text-text-faint transition-colors hover:bg-danger-500/10 hover:text-danger-500"
                                aria-label="Remove user"
                              >
                                <Trash2 className="h-4 w-4" />
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
          </div>
        )}
      </div>

      <CreateUserModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => {
          queryClient.setQueryData<UserOut[]>(['users'], (old = []) => [...old, created])
          setCreateOpen(false)
          toast.push({ tone: 'success', title: `${created.email} added` })
        }}
      />

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Remove user?"
        description={deleting ? `${deleting.email} will lose access to this organization.` : undefined}
        confirmLabel="Remove"
        onConfirm={async () => {
          if (deleting) {
            await deleteMutation.mutateAsync(deleting.id)
            toast.push({ tone: 'success', title: 'User removed' })
          }
        }}
      />
    </div>
  )
}

function CreateUserModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (created: UserOut) => void
}) {
  const [form, setForm] = useState<UserCreate>({ email: '', password: '', full_name: '', role: 'member' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setForm({ email: '', password: '', full_name: '', role: 'member' })
    setError(null)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const created = await usersApi.create({
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name?.trim() || null,
        role: form.role,
      })
      reset()
      onCreated(created)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create user')
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
      title="Invite user"
      description="They can sign in immediately with the password you set here."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Full name"
          value={form.full_name ?? ''}
          onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
        />
        <Input
          label="Email"
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
        />
        <Input
          label="Temporary password"
          type="password"
          required
          minLength={8}
          value={form.password}
          onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-text">Role</label>
          <select
            value={form.role}
            onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserRole }))}
            className="rounded-lg border border-border-strong bg-surface px-3.5 py-2.5 text-[15px] text-text focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {ROLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
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
