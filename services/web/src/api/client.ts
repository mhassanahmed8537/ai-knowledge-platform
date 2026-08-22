import { tokenStore } from './tokenStore'
import type { TokenResponse } from './types'

const BASE_URL = '/api'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function extractMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI/Pydantic validation errors: [{ loc, msg, type }, ...]
    const first = detail[0] as { msg?: string } | undefined
    if (first?.msg) return first.msg
  }
  return fallback
}

let refreshPromise: Promise<boolean> | null = null

/** Refreshes the access token exactly once even if several requests 401 concurrently. */
async function refreshAccessToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    const refreshToken = tokenStore.getRefreshToken()
    if (!refreshToken) return false
    try {
      const res = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) {
        tokenStore.clear()
        return false
      }
      const tokens: TokenResponse = await res.json()
      tokenStore.setTokens(tokens.access_token, tokens.refresh_token)
      return true
    } catch {
      return false
    }
  })()

  try {
    return await refreshPromise
  } finally {
    refreshPromise = null
  }
}

export interface RequestOptions {
  method?: string
  body?: unknown
  /** Skip attaching the Authorization header (signup/login/refresh). */
  anonymous?: boolean
  /** Internal: prevents infinite refresh-retry loops. */
  _retried?: boolean
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, anonymous = false, _retried = false } = options

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (!anonymous) {
    const token = tokenStore.getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !anonymous && !_retried) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      return apiFetch<T>(path, { ...options, _retried: true })
    }
  }

  if (!res.ok) {
    let detail: unknown
    try {
      detail = (await res.json()).detail
    } catch {
      detail = undefined
    }
    throw new ApiError(res.status, extractMessage(detail, res.statusText), detail)
  }

  if (res.status === 204) return undefined as T

  return (await res.json()) as T
}

/** For multipart uploads, which need their own Content-Type boundary. */
export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const token = tokenStore.getAccessToken()
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!res.ok) {
    let detail: unknown
    try {
      detail = (await res.json()).detail
    } catch {
      detail = undefined
    }
    throw new ApiError(res.status, extractMessage(detail, res.statusText), detail)
  }
  return (await res.json()) as T
}

export { BASE_URL }
