import { createContext, use, useCallback, useEffect, useState, type ReactNode } from 'react'
import { authApi } from '@/api/auth'
import { organizationsApi } from '@/api/organizations'
import { tokenStore } from '@/api/tokenStore'
import type { LoginRequest, OrganizationOut, SignupRequest, UserOut } from '@/api/types'

interface AuthContextValue {
  user: UserOut | null
  organization: OrganizationOut | null
  status: 'loading' | 'authenticated' | 'anonymous'
  login: (body: LoginRequest) => Promise<void>
  signup: (body: SignupRequest) => Promise<void>
  logout: () => void
  refreshOrganization: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [organization, setOrganization] = useState<OrganizationOut | null>(null)
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'anonymous'>('loading')

  const loadSession = useCallback(async () => {
    if (!tokenStore.getAccessToken()) {
      setUser(null)
      setOrganization(null)
      setStatus('anonymous')
      return
    }
    try {
      const [me, org] = await Promise.all([authApi.me(), organizationsApi.me()])
      setUser(me)
      setOrganization(org)
      setStatus('authenticated')
    } catch {
      tokenStore.clear()
      setUser(null)
      setOrganization(null)
      setStatus('anonymous')
    }
  }, [])

  useEffect(() => {
    void loadSession()
    return tokenStore.subscribe(() => {
      if (!tokenStore.getAccessToken()) {
        setUser(null)
        setOrganization(null)
        setStatus('anonymous')
      }
    })
  }, [loadSession])

  const login = useCallback(
    async (body: LoginRequest) => {
      const tokens = await authApi.login(body)
      tokenStore.setTokens(tokens.access_token, tokens.refresh_token)
      await loadSession()
    },
    [loadSession],
  )

  const signup = useCallback(
    async (body: SignupRequest) => {
      const tokens = await authApi.signup(body)
      tokenStore.setTokens(tokens.access_token, tokens.refresh_token)
      await loadSession()
    },
    [loadSession],
  )

  const logout = useCallback(() => {
    const refreshToken = tokenStore.getRefreshToken()
    tokenStore.clear()
    setUser(null)
    setOrganization(null)
    setStatus('anonymous')
    if (refreshToken) {
      // Best-effort server-side revocation; the local session is already gone.
      authApi.logout(refreshToken).catch(() => {})
    }
  }, [])

  const refreshOrganization = useCallback(async () => {
    const org = await organizationsApi.me()
    setOrganization(org)
  }, [])

  return (
    <AuthContext value={{ user, organization, status, login, signup, logout, refreshOrganization }}>
      {children}
    </AuthContext>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = use(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
