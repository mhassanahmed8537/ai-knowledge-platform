import { Building2, LogOut, Moon, Sun, UserCircle } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { BudgetEditorModal } from '@/components/BudgetEditorModal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { cn, formatCurrency, formatDate, initials } from '@/lib/utils'

const ROLE_LABEL: Record<string, string> = {
  admin: 'Admin',
  member: 'Member',
  read_only: 'Read only',
}

export function Settings() {
  const { user, organization, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [budgetOpen, setBudgetOpen] = useState(false)

  return (
    <div>
      <PageHeader title="Settings" description="Manage your profile, organization, and appearance." />

      <div className="flex flex-col gap-5 px-6 pb-10 sm:px-8">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Profile</CardTitle>
              <CardDescription>Your account within this organization.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="flex items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-sm font-semibold text-brand-600 dark:text-brand-300">
              {user ? initials(user.full_name ?? user.email) : <UserCircle className="h-6 w-6" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-medium text-text">{user?.full_name ?? user?.email}</p>
              <p className="truncate text-sm text-text-muted">{user?.email}</p>
            </div>
            {user && <Badge tone={user.role === 'admin' ? 'brand' : 'neutral'}>{ROLE_LABEL[user.role]}</Badge>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Organization</CardTitle>
              <CardDescription>Shared across everyone on your team.</CardDescription>
            </div>
            <Building2 className="h-5 w-5 shrink-0 text-text-faint" />
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="text-sm text-text-muted">Name</span>
              <span className="text-sm font-medium text-text">{organization?.name}</span>
            </div>
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="text-sm text-text-muted">Slug</span>
              <span className="text-sm font-medium text-text">{organization?.slug}</span>
            </div>
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="text-sm text-text-muted">Monthly budget</span>
              <span className="text-sm font-medium text-text">
                {organization?.monthly_budget_usd ? formatCurrency(organization.monthly_budget_usd) : 'No limit'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-muted">Created</span>
              <span className="text-sm font-medium text-text">
                {organization && formatDate(organization.created_at)}
              </span>
            </div>
            {user?.role === 'admin' && (
              <div className="mt-1 flex justify-end">
                <Button variant="secondary" size="sm" onClick={() => setBudgetOpen(true)}>
                  Edit budget
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Appearance</CardTitle>
              <CardDescription>Choose how the interface looks on this device.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 rounded-lg border border-border-strong bg-bg p-1 w-fit">
              {(['light', 'dark'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => t !== theme && toggleTheme()}
                  className={cn(
                    'flex items-center gap-2 rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors',
                    theme === t ? 'bg-brand-600 text-white' : 'text-text-muted hover:text-text',
                  )}
                >
                  {t === 'light' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                  {t === 'light' ? 'Light' : 'Dark'}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center justify-between p-5">
            <div>
              <p className="text-[15px] font-medium text-text">Sign out</p>
              <p className="text-sm text-text-muted">End your session on this device.</p>
            </div>
            <Button variant="danger" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </Button>
          </CardContent>
        </Card>
      </div>

      <BudgetEditorModal open={budgetOpen} onClose={() => setBudgetOpen(false)} />
    </div>
  )
}
