import { apiFetch } from './client'
import type { ApiKeyCreate, ApiKeyCreated, ApiKeyOut } from './types'

export const apiKeysApi = {
  list: () => apiFetch<ApiKeyOut[]>('/api-keys'),
  create: (body: ApiKeyCreate) =>
    apiFetch<ApiKeyCreated>('/api-keys', { method: 'POST', body }),
  revoke: (id: string) => apiFetch<void>(`/api-keys/${id}`, { method: 'DELETE' }),
}
