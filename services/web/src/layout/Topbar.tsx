import { AnimatePresence, motion } from 'framer-motion'
import { LogOut, Menu, Moon, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { initials } from '@/lib/utils'

interface TopbarProps {
  onOpenMobile: () => void
}

export function Topbar({ onOpenMobile }: TopbarProps) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [menuOpen])

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border px-4 md:px-6">
      <button
        onClick={onOpenMobile}
        className="rounded-lg p-2 text-text-muted hover:bg-border/40 md:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="hidden md:block" />

      <div className="flex items-center gap-2">
        <button
          onClick={toggleTheme}
          className="rounded-lg p-2 text-text-muted transition-colors hover:bg-border/40 hover:text-text"
          aria-label="Toggle theme"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={theme}
              initial={{ opacity: 0, rotate: -60, scale: 0.7 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: 60, scale: 0.7 }}
              transition={{ duration: 0.18 }}
            >
              {theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
            </motion.div>
          </AnimatePresence>
        </button>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2.5 transition-colors hover:bg-border/40"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/15 text-xs font-semibold text-brand-600 dark:text-brand-300">
              {user ? initials(user.full_name || user.email) : ''}
            </div>
            <span className="hidden max-w-32 truncate text-sm font-medium text-text sm:inline">
              {user?.full_name || user?.email}
            </span>
          </button>
          <AnimatePresence>
            {menuOpen && (
              <motion.div
                initial={{ opacity: 0, y: -6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full z-20 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-surface-raised shadow-[var(--shadow-soft)] dark:shadow-[var(--shadow-soft-dark)]"
              >
                <div className="border-b border-border px-3.5 py-3">
                  <p className="truncate text-sm font-medium text-text">{user?.full_name || 'Account'}</p>
                  <p className="truncate text-xs text-text-faint">{user?.email}</p>
                </div>
                <button
                  onClick={logout}
                  className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-sm text-text-muted transition-colors hover:bg-border/40 hover:text-text"
                >
                  <LogOut className="h-4 w-4" />
                  Log out
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  )
}
