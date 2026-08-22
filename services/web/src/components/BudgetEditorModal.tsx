import { useState, type FormEvent } from 'react'
import { organizationsApi } from '@/api/organizations'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { useAuth } from '@/context/AuthContext'
import { useToast } from '@/context/ToastContext'

export function BudgetEditorModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { organization, refreshOrganization } = useAuth()
  const toast = useToast()
  const [value, setValue] = useState(organization?.monthly_budget_usd ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await organizationsApi.update({ monthly_budget_usd: value.trim() === '' ? null : value.trim() })
      await refreshOrganization()
      toast.push({ tone: 'success', title: 'Budget updated' })
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update budget')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Monthly budget" description="A soft cap on spend — crossing it fires a budget.alert webhook rather than blocking requests.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Budget (USD)"
          type="number"
          min="0"
          step="0.01"
          placeholder="No limit"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        {error && <p className="text-sm text-danger-500">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  )
}
