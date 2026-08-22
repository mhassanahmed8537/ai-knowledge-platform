import { apiFetch } from './client'
import type { LoginRequest, SignupRequest, TokenResponse, UserOut } from './types'

export const authApi = {
  signup: (body: SignupRequest) =>
    apiFetch<TokenResponse>('/auth/signup', { method: 'POST', body, anonymous: true }),

  login: (body: LoginRequest) =>
    apiFetch<TokenResponse>('/auth/login', { method: 'POST', body, anonymous: true }),

  logout: (refreshToken: string) =>
    apiFetch<void>('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } }),

  me: () => apiFetch<UserOut>('/auth/me'),
}
