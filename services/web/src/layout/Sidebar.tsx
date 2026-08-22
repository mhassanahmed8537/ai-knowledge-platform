import { motion } from 'framer-motion'
import {
  Key,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  Sparkles,
  Users,
  Webhook,
  X,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: typeof MessageSquare
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/documents', label: 'Documents', icon: LayoutDashboard },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/usage', label: 'Usage & billing', icon: Sparkles },
  { to: '/webhooks', label: 'Webhooks', icon: Webhook },
  { to: '/api-keys', label: 'API keys', icon: Key },
  { to: '/users', label: 'Team', icon: Users, adminOnly: true },
  { to: '/settings', label: 'Settings', icon: Settings },
]

interface SidebarProps {
  mobileOpen: boolean
  onCloseMobile: () => void
}

export function Sidebar({ mobileOpen, onCloseMobile }: SidebarProps) {
  const { user, organization } = useAuth()

  const items = NAV_ITEMS.filter((item) => !item.adminOnly || user?.role === 'admin')

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={onCloseMobile}
          aria-hidden
        />
      )}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 flex-col border-r border-border bg-surface transition-transform duration-200 md:static md:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-text">
                {organization?.name ?? 'Knowledge Platform'}
              </p>
            </div>
          </div>
          <button
            onClick={onCloseMobile}
            className="rounded-lg p-1.5 text-text-faint hover:bg-border/50 md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'text-brand-600 dark:text-brand-300'
                    : 'text-text-muted hover:bg-border/40 hover:text-text',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active"
                      className="absolute inset-0 rounded-lg bg-brand-500/12"
                      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    />
                  )}
                  <item.icon className="relative h-[18px] w-[18px] shrink-0" />
                  <span className="relative">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
